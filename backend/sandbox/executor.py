"""SandboxExecutor — standalone sidecar HTTP server.

MUST be run as a separate process (never imported by FastAPI):
    python -m sandbox.executor

Security model:
  - Binds ONLY to 127.0.0.1 — never 0.0.0.0
  - All requests require X-Sandbox-Secret header (validated on every route)
  - Each execution runs in an ephemeral Docker container
  - Containers are network-isolated (--network none)
  - Memory and CPU are bounded per container
  - A hard wall-clock timeout kills the container unconditionally
  - A background reaper thread purges stale/zombie containers every 30s

Concurrency:
  - MAX_CONCURRENT_CONTAINERS caps simultaneous executions (default: 5)
  - Requests beyond the limit receive 503 immediately (no queuing)

Trusted mode exception:
  - When SANDBOX_TRUSTED_MODE=true the sidecar uses a local subprocess.
  - This mode is ONLY for development/CI test fixtures running pre-reviewed
    test code. It MUST NEVER be used with user-submitted or LLM-generated code.

Docker image:
  - The default image is testgen-sandbox:latest — a custom image built from
    backend/sandbox/Dockerfile that has pytest pre-installed.
  - Build it once before starting the executor:
      cd backend && docker build -t testgen-sandbox:latest ./sandbox
  - Override with SANDBOX_DOCKER_IMAGE env var if needed.
  - Never use python:3.11-slim directly — it does not include pytest.

Configuration (environment variables):
  SANDBOX_SECRET                    — shared secret (REQUIRED)
  SANDBOX_BIND_HOST                 — default: 127.0.0.1
  SANDBOX_BIND_PORT                 — default: 8001
  SANDBOX_MAX_CONCURRENT_CONTAINERS — default: 5
  SANDBOX_TIMEOUT_SECONDS           — default: 10
  SANDBOX_MEMORY_MB                 — default: 128
  SANDBOX_DOCKER_IMAGE              — default: testgen-sandbox:latest
  SANDBOX_TRUSTED_MODE              — default: false  (NEVER true in production)
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager

_COV_START = "___COVERAGE_JSON_START___"
_COV_END = "___COVERAGE_JSON_END___"


def _extract_coverage_metrics(
    raw_stdout: str,
    target_filename: str | None = None,
) -> tuple[str, dict]:
    """Parse coverage JSON block from stdout and dynamically extract source metrics.

    Returns a tuple of (clean_stdout, metrics_dict).
    If parsing fails or delimiter is missing, clean_stdout is raw_stdout
    and metrics_dict is empty (all coverage fields evaluate to None).
    """
    if _COV_START not in raw_stdout or _COV_END not in raw_stdout:
        return raw_stdout, {}

    try:
        before, rest = raw_stdout.split(_COV_START, 1)
        json_str, after = rest.split(_COV_END, 1)
        clean_stdout = (before.rstrip() + "\n" + after.lstrip()).strip()

        cov_data = json.loads(json_str.strip())
        files_dict = cov_data.get("files", {})

        source_entry = None
        matched_filename = None

        # 1. Try matching target_filename dynamically
        if target_filename:
            for fname, entry in files_dict.items():
                if fname.endswith(target_filename) or os.path.basename(fname) == target_filename:
                    source_entry = entry
                    matched_filename = os.path.basename(fname)
                    break

        # 2. Dynamic fallback: first non-test Python file
        if not source_entry:
            for fname, entry in files_dict.items():
                basename = os.path.basename(fname)
                if not basename.startswith("test_") and basename != "test_code.py":
                    source_entry = entry
                    matched_filename = basename
                    break

        if not source_entry:
            log.info("coverage_file_not_identified files=%s", list(files_dict.keys()))
            return clean_stdout, {}

        summary = source_entry.get("summary", {})
        num_statements = summary.get("num_statements", 0)
        covered_lines = summary.get("covered_lines", 0)
        missing_lines = summary.get("missing_lines", 0)
        percent_covered = summary.get("percent_covered", 0.0)

        num_branches = summary.get("num_branches", 0)
        covered_branches = summary.get("covered_branches", 0)

        branch_pct = 100.0
        if num_branches > 0:
            branch_pct = round((covered_branches / num_branches) * 100, 2)

        line_pct = round(float(percent_covered), 2)

        log.info(
            "coverage_report_generated source_file=%s line_coverage=%.1f%% branch_coverage=%.1f%% total_statements=%d covered=%d missing=%d",
            matched_filename,
            line_pct,
            branch_pct,
            num_statements,
            covered_lines,
            missing_lines,
        )

        return clean_stdout, {
            "coverage_line_pct": line_pct,
            "coverage_branch_pct": branch_pct,
            "coverage_total_statements": int(num_statements),
            "coverage_covered_statements": int(covered_lines),
            "coverage_missing_statements": int(missing_lines),
        }

    except Exception as exc:
        log.warning("coverage_parse_failed error=%s", exc)
        return raw_stdout, {}

# ---------------------------------------------------------------------------
# Load .env before reading os.environ.
#
# The executor is a standalone process — it does NOT go through pydantic-settings,
# so values in .env are never automatically visible via os.environ.
# python-dotenv is a transitive dependency of pydantic-settings (already in venv).
# override=False means shell-exported vars take precedence over .env values.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(override=False)
except ImportError:
    pass  # dotenv not available — fall back to raw os.environ (CI/Docker pass vars directly)

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

# IPC schemas shared with the FastAPI-side SandboxClient
from app.sandbox.schemas import (
    SANDBOX_UNAVAILABLE_EXIT_CODE,
    SandboxExecuteRequest,
    SandboxExecuteResponse,
)

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

_SECRET: str = os.environ.get(
    "SANDBOX_SECRET", "CHANGE_THIS_SANDBOX_SECRET_IN_PRODUCTION"
)
_BIND_HOST: str = os.environ.get("SANDBOX_BIND_HOST", "127.0.0.1")
_BIND_PORT: int = int(os.environ.get("SANDBOX_BIND_PORT", "8001"))
_MAX_CONCURRENT: int = int(os.environ.get("SANDBOX_MAX_CONCURRENT_CONTAINERS", "5"))
_TIMEOUT_SECONDS: int = int(os.environ.get("SANDBOX_TIMEOUT_SECONDS", "60"))
_MEMORY_MB: int = int(os.environ.get("SANDBOX_MEMORY_MB", "128"))
_DOCKER_IMAGE: str = os.environ.get("SANDBOX_DOCKER_IMAGE", "python:3.11-slim")
_TRUSTED_MODE: bool = (
    os.environ.get("SANDBOX_TRUSTED_MODE", "false").lower() == "true"
)

# ---------------------------------------------------------------------------
# Concurrency control
# ---------------------------------------------------------------------------

_semaphore = threading.Semaphore(_MAX_CONCURRENT)
_active_containers: dict[str, float] = {}  # container_name -> start_time (monotonic)
_containers_lock = threading.Lock()

log = logging.getLogger("sandbox.executor")


# ---------------------------------------------------------------------------
# Background container reaper
# ---------------------------------------------------------------------------


def _reap_stale_containers() -> None:
    """Daemon thread: kill containers that have outlived their timeout.

    Runs every 30 seconds. Targets containers alive more than
    TIMEOUT + 10 seconds to handle cases where the main thread
    was interrupted before cleaning up.
    """
    cutoff = _TIMEOUT_SECONDS + 10
    while True:
        time.sleep(30)
        now = time.monotonic()
        with _containers_lock:
            stale = [cid for cid, t in _active_containers.items() if now - t > cutoff]

        for cid in stale:
            log.warning("reaper_killing_stale_container container_id=%s", cid)
            try:
                subprocess.run(["docker", "kill", cid], capture_output=True, timeout=5)
                subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=5)
            except Exception as exc:
                log.error("reaper_kill_failed container_id=%s error=%s", cid, exc)
            finally:
                with _containers_lock:
                    _active_containers.pop(cid, None)


# ---------------------------------------------------------------------------
# Trusted mode execution (DEVELOPMENT / CI ONLY — never for LLM output)
# ---------------------------------------------------------------------------


def _run_trusted(
    code: str,
    timeout: int,
    source_code: str | None = None,
    source_filename: str = "main.py",
) -> SandboxExecuteResponse:
    """Execute code via OS subprocess.

    *** TRUSTED DEVELOPMENT / TEST FIXTURE MODE ONLY ***
    MUST NEVER execute arbitrary user-submitted or LLM-generated code.
    """
    log.warning("TRUSTED_MODE_EXECUTION — verify code is pre-reviewed before use")
    start = time.monotonic()

    temp_dir = tempfile.mkdtemp(prefix="sandbox_trusted_")
    test_file_path = os.path.join(temp_dir, "test_code.py")

    try:
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(code)

        if source_code is not None:
            src_file_path = os.path.join(temp_dir, source_filename)
            with open(src_file_path, "w", encoding="utf-8") as sf:
                sf.write(source_code)

        result = subprocess.run(
            ["python", "-m", "pytest", test_file_path, "--tb=short", "-q", "--no-header"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=temp_dir,
        )
        duration_ms = (time.monotonic() - start) * 1000
        return SandboxExecuteResponse(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired:
        duration_ms = (time.monotonic() - start) * 1000
        return SandboxExecuteResponse(
            exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
            stdout="",
            stderr="Trusted-mode execution timed out",
            duration_ms=duration_ms,
            error="TIMEOUT",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Containerised execution
# ---------------------------------------------------------------------------


def _run_containerised(
    code: str,
    timeout: int,
    source_code: str | None = None,
    source_filename: str = "main.py",
) -> SandboxExecuteResponse:
    """Execute code inside an ephemeral Docker container.

    Security constraints applied:
      --network none          — no outbound connectivity
      --memory               — hard memory cap
      --memory-swap=0        — no swap
      --cpus=0.5             — bounded CPU
      --read-only            — immutable root filesystem
      --tmpfs=/tmp           — writable scratch space only
      --security-opt no-new-privileges
      --rm                   — auto-remove on exit
      wall-clock timeout     — unconditional SIGKILL via subprocess timeout
    """
    container_id = f"testgen-sandbox-{uuid.uuid4().hex[:12]}"
    start = time.monotonic()

    with _containers_lock:
        _active_containers[container_id] = start

    tmp_path = None
    src_tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        docker_cmd = [
            "docker", "run",
            "--rm",
            f"--name={container_id}",
            "--network=none",
            f"--memory={_MEMORY_MB}m",
            "--memory-swap=0",
            "--cpus=0.5",
            "--read-only",
            "--tmpfs=/tmp:size=64m",
            "--security-opt=no-new-privileges",
            f"-v={tmp_path}:/test_code.py:ro",
        ]

        if source_code is not None:
            with tempfile.NamedTemporaryFile(
                suffix=".py", mode="w", delete=False, encoding="utf-8"
            ) as sf:
                sf.write(source_code)
                src_tmp_path = sf.name
            docker_cmd.append(f"-v={src_tmp_path}:/{source_filename}:ro")

        docker_cmd.extend([
            "-e", "COVERAGE_FILE=/tmp/.coverage",
            _DOCKER_IMAGE,
            "sh", "-c",
            "python -m coverage run --branch -m pytest /test_code.py --tb=short -q --no-header -p no:cacheprovider; "
            "EC=$?; "
            "python -m coverage json -o /tmp/coverage.json >/dev/null 2>&1; "
            "if [ -f /tmp/coverage.json ]; then "
            f"echo '{_COV_START}'; cat /tmp/coverage.json; echo ''; echo '{_COV_END}'; "
            "fi; "
            "exit $EC",
        ])

        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.monotonic() - start) * 1000
            clean_stdout, cov_metrics = _extract_coverage_metrics(
                proc.stdout, target_filename=source_filename
            )
            return SandboxExecuteResponse(
                exit_code=proc.returncode,
                stdout=clean_stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                **cov_metrics,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.monotonic() - start) * 1000
            log.warning("container_timeout container_id=%s", container_id)
            # Kill the container unconditionally
            try:
                subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=5)
            except Exception:
                pass
            return SandboxExecuteResponse(
                exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
                stdout="",
                stderr=f"Container exceeded wall-clock timeout of {timeout}s and was killed",
                duration_ms=duration_ms,
                error="TIMEOUT",
            )

    except FileNotFoundError:
        # docker CLI not found on PATH
        duration_ms = (time.monotonic() - start) * 1000
        log.error("docker_not_found")
        return SandboxExecuteResponse(
            exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
            stdout="",
            stderr="Docker runtime not found — is Docker installed and running?",
            duration_ms=duration_ms,
            error="SANDBOX_UNAVAILABLE",
        )

    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        log.error("container_runtime_error error=%s", exc)
        return SandboxExecuteResponse(
            exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
            stdout="",
            stderr=f"Container runtime error: {exc}",
            duration_ms=duration_ms,
            error="SANDBOX_UNAVAILABLE",
        )

    finally:
        with _containers_lock:
            _active_containers.pop(container_id, None)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if src_tmp_path:
            try:
                os.unlink(src_tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Start the background reaper daemon on startup."""
    reaper = threading.Thread(target=_reap_stale_containers, daemon=True, name="container-reaper")
    reaper.start()
    log.info(
        "sandbox_executor_started host=%s port=%s trusted_mode=%s max_concurrent=%s",
        _BIND_HOST, _BIND_PORT, _TRUSTED_MODE, _MAX_CONCURRENT,
    )
    yield


executor_app = FastAPI(
    title="TestGen AI Sandbox Executor",
    description="Isolated container execution service for pytest",
    version="1.0.0",
    lifespan=_lifespan,
)


@executor_app.get(
    "/health",
    response_model=dict,
    summary="Health check endpoint",
)
async def health_check(
    x_sandbox_secret: str = Header(alias="X-Sandbox-Secret"),
) -> JSONResponse:
    """Return 200 when the sidecar is alive and accepting requests."""
    if x_sandbox_secret != _SECRET:
        raise HTTPException(status_code=401, detail="Invalid sandbox secret")
    return JSONResponse({
        "status": "alive",
        "trusted_mode": _TRUSTED_MODE,
        "max_concurrent": _MAX_CONCURRENT,
        "timeout_seconds": _TIMEOUT_SECONDS,
    })


@executor_app.post(
    "/execute",
    response_model=SandboxExecuteResponse,
    summary="Execute pytest code in an isolated container",
)
async def execute_code(
    request: SandboxExecuteRequest,
    x_sandbox_secret: str = Header(alias="X-Sandbox-Secret"),
) -> SandboxExecuteResponse:
    """Run pytest code inside an ephemeral container and return the result.

    Returns SandboxExecuteResponse.
    Never raises — unreachable runtime returns exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE.
    """
    if x_sandbox_secret != _SECRET:
        raise HTTPException(status_code=401, detail="Invalid sandbox secret")

    # Check concurrency limit — fail fast, never queue
    acquired = _semaphore.acquire(blocking=False)
    if not acquired:
        log.warning("sandbox_concurrency_limit_reached max_concurrent=%s", _MAX_CONCURRENT)
        return SandboxExecuteResponse(
            exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
            stdout="",
            stderr=f"Sandbox concurrency limit ({_MAX_CONCURRENT}) reached — try again later",
            duration_ms=0.0,
            error="SANDBOX_UNAVAILABLE",
        )

    try:
        if _TRUSTED_MODE:
            return _run_trusted(
                code=request.code,
                timeout=request.timeout_seconds,
                source_code=request.source_code,
                source_filename=request.source_filename,
            )
        return _run_containerised(
            code=request.code,
            timeout=request.timeout_seconds,
            source_code=request.source_code,
            source_filename=request.source_filename,
        )
    finally:
        _semaphore.release()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(
        executor_app,
        host=_BIND_HOST,
        port=_BIND_PORT,
        log_level="info",
    )
