"""Tests for Phase 2 sandbox components.

Tests:
  - SandboxExecuteRequest / SandboxExecuteResponse schemas
  - SandboxClient (connection refused → SANDBOX_UNAVAILABLE)
  - SandboxClient (timeout → TIMEOUT error)
  - SandboxClient (non-200 response handling)
  - SandboxClient.health_check (sidecar unreachable)
  - Executor secret validation
  - Executor concurrency limit sentinel
  - Configuration values
"""

import json
import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.sandbox.schemas import (
    SANDBOX_UNAVAILABLE_EXIT_CODE,
    SandboxExecuteRequest,
    SandboxExecuteResponse,
)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSandboxSchemas:
    """SandboxExecuteRequest and SandboxExecuteResponse schema validation."""

    def test_request_requires_code(self) -> None:
        req = SandboxExecuteRequest(code="def test_foo(): assert 1 == 1")
        assert req.code == "def test_foo(): assert 1 == 1"
        assert req.framework == "pytest"
        assert req.timeout_seconds == 5

    def test_request_custom_timeout(self) -> None:
        req = SandboxExecuteRequest(code="pass", timeout_seconds=30)
        assert req.timeout_seconds == 30

    def test_request_timeout_min_is_1(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SandboxExecuteRequest(code="pass", timeout_seconds=0)

    def test_request_timeout_max_is_120(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SandboxExecuteRequest(code="pass", timeout_seconds=121)

    def test_response_all_fields(self) -> None:
        resp = SandboxExecuteResponse(
            exit_code=0,
            stdout="1 passed",
            stderr="",
            duration_ms=142.5,
        )
        assert resp.exit_code == 0
        assert resp.stdout == "1 passed"
        assert resp.duration_ms == 142.5
        assert resp.error is None

    def test_response_error_field(self) -> None:
        resp = SandboxExecuteResponse(
            exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
            stdout="",
            stderr="connection refused",
            duration_ms=0.1,
            error="SANDBOX_UNAVAILABLE",
        )
        assert resp.exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE
        assert resp.error == "SANDBOX_UNAVAILABLE"

    def test_unavailable_exit_code_is_minus_one(self) -> None:
        assert SANDBOX_UNAVAILABLE_EXIT_CODE == -1

    def test_response_json_roundtrip(self) -> None:
        resp = SandboxExecuteResponse(
            exit_code=1, stdout="F", stderr="AssertionError", duration_ms=99.0
        )
        data = json.loads(resp.model_dump_json())
        restored = SandboxExecuteResponse(**data)
        assert restored.exit_code == 1

    def test_response_coverage_fields_default_to_none(self) -> None:
        resp = SandboxExecuteResponse(
            exit_code=0, stdout="passed", stderr="", duration_ms=100.0
        )
        assert resp.coverage_line_pct is None
        assert resp.coverage_branch_pct is None
        assert resp.coverage_total_statements is None
        assert resp.coverage_covered_statements is None
        assert resp.coverage_missing_statements is None

    def test_response_coverage_fields_population(self) -> None:
        resp = SandboxExecuteResponse(
            exit_code=0,
            stdout="passed",
            stderr="",
            duration_ms=150.0,
            coverage_line_pct=85.5,
            coverage_branch_pct=80.0,
            coverage_total_statements=20,
            coverage_covered_statements=17,
            coverage_missing_statements=3,
        )
        assert resp.coverage_line_pct == 85.5
        assert resp.coverage_branch_pct == 80.0
        assert resp.coverage_total_statements == 20
        assert resp.coverage_covered_statements == 17
        assert resp.coverage_missing_statements == 3


class TestCoverageExtraction:
    """Tests for dynamic source file detection and coverage JSON parsing in executor."""

    def test_extract_coverage_metrics_dynamic_filename(self) -> None:
        from sandbox.executor import _COV_END, _COV_START, _extract_coverage_metrics

        raw_cov_json = json.dumps({
            "files": {
                "/calculator.py": {
                    "summary": {
                        "num_statements": 10,
                        "covered_lines": 9,
                        "missing_lines": 1,
                        "percent_covered": 90.0,
                        "num_branches": 4,
                        "covered_branches": 3,
                    }
                },
                "/test_code.py": {
                    "summary": {
                        "num_statements": 5,
                        "covered_lines": 5,
                        "missing_lines": 0,
                        "percent_covered": 100.0,
                    }
                }
            }
        })

        stdout = f"pytest output line\n{_COV_START}\n{raw_cov_json}\n{_COV_END}\nDone"
        clean_stdout, metrics = _extract_coverage_metrics(stdout, target_filename="calculator.py")

        assert clean_stdout == "pytest output line\nDone"
        assert metrics["coverage_line_pct"] == 90.0
        assert metrics["coverage_branch_pct"] == 75.0
        assert metrics["coverage_total_statements"] == 10
        assert metrics["coverage_covered_statements"] == 9
        assert metrics["coverage_missing_statements"] == 1

    def test_extract_coverage_metrics_fallback_dynamic_detection(self) -> None:
        from sandbox.executor import _COV_END, _COV_START, _extract_coverage_metrics

        raw_cov_json = json.dumps({
            "files": {
                "/custom_module.py": {
                    "summary": {
                        "num_statements": 15,
                        "covered_lines": 15,
                        "missing_lines": 0,
                        "percent_covered": 100.0,
                        "num_branches": 0,
                        "covered_branches": 0,
                    }
                }
            }
        })

        stdout = f"{_COV_START}\n{raw_cov_json}\n{_COV_END}"
        clean_stdout, metrics = _extract_coverage_metrics(stdout, target_filename=None)

        assert metrics["coverage_line_pct"] == 100.0
        assert metrics["coverage_branch_pct"] == 100.0
        assert metrics["coverage_total_statements"] == 15

    def test_extract_coverage_metrics_graceful_failure_on_bad_json(self) -> None:
        from sandbox.executor import _COV_END, _COV_START, _extract_coverage_metrics

        stdout = f"{_COV_START}\nINVALID_JSON\n{_COV_END}"
        clean_stdout, metrics = _extract_coverage_metrics(stdout)
        assert metrics == {}


# ---------------------------------------------------------------------------
# SandboxClient tests
# ---------------------------------------------------------------------------


class TestSandboxClient:
    """SandboxClient behaviour without a real sidecar running."""

    def _make_client(self, **kwargs):
        from app.sandbox.client import SandboxClient
        return SandboxClient(
            base_url="http://127.0.0.1:19999",  # port nothing listens on
            secret="test-secret",
            timeout_seconds=2,
            **kwargs,
        )

    def test_connection_refused_returns_unavailable(self) -> None:
        """When the sidecar is not running, client returns a 'sidecar unavailable' response.

        On Linux: ConnectError is raised immediately → error == SANDBOX_UNAVAILABLE.
        On Windows: the TCP stack times out instead → error == TIMEOUT.
        Both are valid 'sidecar unreachable' signals.
        The critical invariant is exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE.
        """
        client = self._make_client()
        req = SandboxExecuteRequest(code="pass")
        result = client.execute(req)
        assert result.exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE
        assert result.error in ("SANDBOX_UNAVAILABLE", "TIMEOUT"), (
            f"Unexpected error classification: {result.error!r}"
        )

    def test_connection_refused_never_raises(self) -> None:
        """execute() must never raise — errors are captured in the response."""
        client = self._make_client()
        req = SandboxExecuteRequest(code="pass")
        try:
            client.execute(req)
        except Exception as exc:
            pytest.fail(f"execute() raised unexpectedly: {exc}")

    def test_timeout_returns_timeout_error(self) -> None:
        """When httpx times out, client returns TIMEOUT error."""
        from app.sandbox.client import SandboxClient

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.side_effect = httpx.TimeoutException("timed out")

            client = SandboxClient(
                base_url="http://127.0.0.1:8001",
                secret="secret",
                timeout_seconds=5,
            )
            result = client.execute(SandboxExecuteRequest(code="pass"))

        assert result.error == "TIMEOUT"
        assert result.exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE

    def test_non_200_response_returns_runtime_error(self) -> None:
        """A non-200 HTTP response from the sidecar is classified as RUNTIME_ERROR."""
        from app.sandbox.client import SandboxClient

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.return_value = mock_response

            client = SandboxClient(
                base_url="http://127.0.0.1:8001",
                secret="secret",
                timeout_seconds=5,
            )
            result = client.execute(SandboxExecuteRequest(code="pass"))

        assert result.error == "RUNTIME_ERROR"
        assert result.exit_code == 1

    def test_successful_response_parsed_correctly(self) -> None:
        """A valid 200 response is parsed into a SandboxExecuteResponse."""
        from app.sandbox.client import SandboxClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "exit_code": 0,
            "stdout": "1 passed",
            "stderr": "",
            "duration_ms": 123.4,
            "error": None,
        }

        with patch("httpx.Client") as mock_client_cls:
            mock_ctx = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.post.return_value = mock_response

            client = SandboxClient(
                base_url="http://127.0.0.1:8001",
                secret="secret",
                timeout_seconds=5,
            )
            result = client.execute(SandboxExecuteRequest(code="pass"))

        assert result.exit_code == 0
        assert result.stdout == "1 passed"
        assert result.duration_ms == 123.4
        assert result.error is None

    def test_health_check_returns_false_when_unreachable(self) -> None:
        """health_check() must return False when the sidecar is not running."""
        client = self._make_client()
        result = client.health_check()
        assert result is False

    def test_client_sends_correct_secret_header(self) -> None:
        """The X-Sandbox-Secret header must be set on every execute() call."""
        from app.sandbox.client import SandboxClient, _AUTH_HEADER

        captured_headers: list[dict] = []

        def fake_post(url, content=None, headers=None, **kwargs):
            captured_headers.append(dict(headers or {}))
            raise httpx.ConnectError("simulated")

        with patch("httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value.__enter__ = MagicMock(return_value=mock_instance)
            mock_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post = fake_post

            client = SandboxClient(
                base_url="http://127.0.0.1:8001",
                secret="my-test-secret",
                timeout_seconds=5,
            )
            client.execute(SandboxExecuteRequest(code="pass"))

        assert len(captured_headers) == 1
        assert captured_headers[0].get(_AUTH_HEADER) == "my-test-secret"

    def test_duration_ms_is_populated(self) -> None:
        """duration_ms must be a positive float even on connection failure."""
        client = self._make_client()
        result = client.execute(SandboxExecuteRequest(code="pass"))
        # Some time must have elapsed even if it's just 1ms
        assert isinstance(result.duration_ms, float)
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Executor secret validation (unit tests — no actual server started)
# ---------------------------------------------------------------------------


class TestExecutorSecretValidation:
    """Validate the executor's secret-checking logic directly."""

    def test_correct_secret_passes(self) -> None:
        """_check_secret should not raise when the secret matches."""
        import os

        with patch.dict(os.environ, {"SANDBOX_SECRET": "expected-secret"}):
            # Reload the executor module to pick up env changes
            import importlib
            import sandbox.executor as exec_mod
            importlib.reload(exec_mod)
            # If SANDBOX_SECRET matches, health_check endpoint returns 200
            # We test this via the app directly
            from fastapi.testclient import TestClient as TC
            with TC(exec_mod.executor_app) as c:
                r = c.get(
                    "/health",
                    headers={"X-Sandbox-Secret": "expected-secret"},
                )
                assert r.status_code == 200

    def test_wrong_secret_returns_401(self) -> None:
        """Requests with wrong secret must return 401."""
        import os
        import importlib
        import sandbox.executor as exec_mod
        importlib.reload(exec_mod)

        from fastapi.testclient import TestClient as TC
        with TC(exec_mod.executor_app) as c:
            r = c.get(
                "/health",
                headers={"X-Sandbox-Secret": "wrong-secret"},
            )
            assert r.status_code == 401

    def test_missing_secret_header_returns_422(self) -> None:
        """Requests with no X-Sandbox-Secret header return 422 (missing required header)."""
        import importlib
        import sandbox.executor as exec_mod
        importlib.reload(exec_mod)

        from fastapi.testclient import TestClient as TC
        with TC(exec_mod.executor_app) as c:
            r = c.get("/health")
            assert r.status_code == 422


# ---------------------------------------------------------------------------
# Executor concurrency limit
# ---------------------------------------------------------------------------


class TestExecutorConcurrencyLimit:
    """Executor must reject requests when concurrency limit is reached."""

    def test_concurrency_limit_returns_unavailable(self) -> None:
        """When semaphore is exhausted, execute_code returns SANDBOX_UNAVAILABLE."""
        import importlib
        import os
        import sandbox.executor as exec_mod
        importlib.reload(exec_mod)

        # Drain the semaphore completely
        acquired = []
        limit = exec_mod._MAX_CONCURRENT
        for _ in range(limit):
            ok = exec_mod._semaphore.acquire(blocking=False)
            if ok:
                acquired.append(True)

        try:
            from fastapi.testclient import TestClient as TC
            secret = exec_mod._SECRET
            with TC(exec_mod.executor_app) as c:
                r = c.post(
                    "/execute",
                    json={"code": "pass", "framework": "pytest", "timeout_seconds": 5},
                    headers={"X-Sandbox-Secret": secret},
                )
                assert r.status_code == 200
                body = r.json()
                assert body["exit_code"] == SANDBOX_UNAVAILABLE_EXIT_CODE
                assert body["error"] == "SANDBOX_UNAVAILABLE"
        finally:
            # Release the acquired semaphore slots
            for _ in acquired:
                exec_mod._semaphore.release()


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestSandboxConfiguration:
    """Verify Phase 2 settings are present and have correct defaults."""

    def test_jwt_secret_key_exists(self) -> None:
        from app.core.config import settings
        assert isinstance(settings.JWT_SECRET_KEY, str)
        assert len(settings.JWT_SECRET_KEY) > 10

    def test_jwt_algorithm_is_hs256(self) -> None:
        from app.core.config import settings
        assert settings.JWT_ALGORITHM == "HS256"

    def test_jwt_expire_hours_is_24(self) -> None:
        from app.core.config import settings
        assert settings.JWT_ACCESS_TOKEN_EXPIRE_HOURS == 24

    def test_sandbox_url_is_loopback(self) -> None:
        from app.core.config import settings
        assert "127.0.0.1" in settings.SANDBOX_URL or "localhost" in settings.SANDBOX_URL

    def test_sandbox_secret_exists(self) -> None:
        from app.core.config import settings
        assert isinstance(settings.SANDBOX_SECRET, str)
        assert len(settings.SANDBOX_SECRET) > 5

    def test_sandbox_timeout_positive(self) -> None:
        from app.core.config import settings
        assert settings.SANDBOX_TIMEOUT_SECONDS > 0

    def test_sandbox_max_concurrent_positive(self) -> None:
        from app.core.config import settings
        assert settings.SANDBOX_MAX_CONCURRENT_CONTAINERS > 0

    def test_sandbox_memory_mb_positive(self) -> None:
        from app.core.config import settings
        assert settings.SANDBOX_CONTAINER_MEMORY_MB > 0

    def test_enable_auth_is_true(self) -> None:
        from app.core.config import settings
        assert settings.ENABLE_AUTH is True
