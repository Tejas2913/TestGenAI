"""Sandbox IPC contract schemas — Phase 2.

These Pydantic models define the exact request/response contract
between the FastAPI application and the SandboxExecutor sidecar.

Architecture-defined contract:
  Request:  POST /execute
    Body: { "code": "...", "framework": "pytest", "timeout_seconds": 5 }

  Response:
    { "exit_code": 0, "stdout": "...", "stderr": "...", "duration_ms": 142.5 }

Both the SandboxClient (app/sandbox/client.py) and the SandboxExecutor
(sandbox/executor.py) import from this module to guarantee consistency.

SANDBOX_UNAVAILABLE is the sentinel exit_code when the container runtime
is unreachable. Phase 3 pipeline uses this to fail the job gracefully.
"""

from pydantic import BaseModel, Field

# Sentinel exit code returned when the container runtime is unavailable.
# Distinct from OS exit codes (0 = success, 1 = test failures, 2 = error).
SANDBOX_UNAVAILABLE_EXIT_CODE = -1


class SandboxExecuteRequest(BaseModel):
    """Request payload sent by FastAPI to the SandboxExecutor sidecar.

    Fields:
        code             — The pytest source code string to execute.
        source_code      — Original Python source code being tested (optional).
        source_filename  — Target filename for source code inside container (default: 'main.py').
        framework        — Test framework (only "pytest" supported in V2.1).
        timeout_seconds  — Hard wall-clock timeout for the container.
    """

    code: str = Field(description="pytest source code to execute inside the container")
    source_code: str | None = Field(
        default=None,
        description="Original Python source code being tested",
    )
    source_filename: str = Field(
        default="main.py",
        description="Target filename for original source code inside container",
    )
    framework: str = Field(
        default="pytest",
        description="Test framework to invoke (V2.1 supports 'pytest' only)",
    )
    timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=120,
        description="Hard wall-clock timeout for container execution",
    )


class SandboxExecuteResponse(BaseModel):
    """Response payload returned by the SandboxExecutor sidecar.

    Fields:
        exit_code    — Process exit code: 0=success, 1=test failure,
                       2=collection error, -1=SANDBOX_UNAVAILABLE.
        stdout       — Captured stdout from the test run.
        stderr       — Captured stderr (tracebacks, import errors, etc).
        duration_ms  — Wall-clock time in milliseconds.
        error        — Optional error classification string:
                       "SANDBOX_UNAVAILABLE", "TIMEOUT", "RUNTIME_ERROR", or None.
    """

    exit_code: int = Field(description="Container process exit code (-1 = unavailable)")
    stdout: str = Field(default="", description="Captured stdout")
    stderr: str = Field(default="", description="Captured stderr")
    duration_ms: float = Field(description="Execution wall-clock time in milliseconds")
    error: str | None = Field(
        default=None,
        description="Error classification: SANDBOX_UNAVAILABLE, TIMEOUT, RUNTIME_ERROR, or None",
    )

    # Coverage metrics (populated when coverage.py execution succeeds)
    coverage_line_pct: float | None = Field(
        default=None, description="Line coverage percentage (0.0 to 100.0)"
    )
    coverage_branch_pct: float | None = Field(
        default=None, description="Branch coverage percentage (0.0 to 100.0)"
    )
    coverage_total_statements: int | None = Field(
        default=None, description="Total executable statements in target source code"
    )
    coverage_covered_statements: int | None = Field(
        default=None, description="Executable statements covered by tests"
    )
    coverage_missing_statements: int | None = Field(
        default=None, description="Executable statements missed by tests"
    )
