"""SandboxClient — FastAPI-side abstraction for the SandboxExecutor sidecar.

Phase 2: This client is implemented and testable.
Phase 3: GenerationService will call execute() during the pipeline.

Architecture contract:
  - Transport: loopback HTTP to 127.0.0.1 only
  - Auth header: X-Sandbox-Secret: <shared secret>
  - Body: SandboxExecuteRequest (JSON)
  - Response: SandboxExecuteResponse (JSON)
  - Timeout: configurable via settings.SANDBOX_TIMEOUT_SECONDS

When the sidecar is unreachable (connection refused, timeout), the client
returns a SandboxExecuteResponse with exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE
rather than raising, so the caller can fail gracefully.
"""

import time

import httpx
import structlog

from app.core.config import settings
from app.sandbox.schemas import (
    SANDBOX_UNAVAILABLE_EXIT_CODE,
    SandboxExecuteRequest,
    SandboxExecuteResponse,
)

logger = structlog.get_logger()

# Header name for sidecar shared secret authentication.
_AUTH_HEADER = "X-Sandbox-Secret"


class SandboxClient:
    """HTTP client for the SandboxExecutor sidecar.

    This class is the sole point of contact between the FastAPI application
    and the isolated execution environment. GenerationService must NOT
    bypass this class to call the sidecar directly.

    Usage (Phase 3):
        client = SandboxClient()
        result = client.execute(SandboxExecuteRequest(code="..."))
        if result.exit_code == 0:
            # tests passed
        elif result.exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE:
            # sidecar unavailable — fail the job gracefully

    The client is stateless and safe to instantiate per-request or as a singleton.
    """

    def __init__(
        self,
        base_url: str | None = None,
        secret: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            base_url:        Sidecar base URL (defaults to settings.SANDBOX_URL).
            secret:          Shared secret (defaults to settings.SANDBOX_SECRET).
            timeout_seconds: Per-request timeout (defaults to settings.SANDBOX_TIMEOUT_SECONDS + 2s buffer).
        """
        self._base_url = (base_url or settings.SANDBOX_URL).rstrip("/")
        self._secret = secret or settings.SANDBOX_SECRET
        # Add a 2-second buffer over the container timeout so the HTTP
        # client doesn't race with the container's wall-clock cutoff.
        self._timeout = timeout_seconds or (settings.SANDBOX_TIMEOUT_SECONDS + 2)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            _AUTH_HEADER: self._secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def execute(self, request: SandboxExecuteRequest) -> SandboxExecuteResponse:
        """Send a code execution request to the SandboxExecutor.

        This is a synchronous blocking call. Phase 3 will offload it to a
        worker thread via anyio.to_thread.run_sync.

        Args:
            request: SandboxExecuteRequest with the code and timeout.

        Returns:
            SandboxExecuteResponse — never raises. Unreachable sidecar
            returns exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE.
        """
        url = f"{self._base_url}/execute"
        start = time.monotonic()

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    url,
                    content=request.model_dump_json(),
                    headers=self._headers,
                )
            duration_ms = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                return SandboxExecuteResponse(**data)

            # Non-200 from sidecar — treat as runtime error
            logger.warning(
                "sandbox_non_200",
                status=response.status_code,
                body=response.text[:200],
            )
            return SandboxExecuteResponse(
                exit_code=1,
                stdout="",
                stderr=f"Sidecar returned HTTP {response.status_code}",
                duration_ms=duration_ms,
                error="RUNTIME_ERROR",
            )

        except httpx.TimeoutException:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("sandbox_client_timeout", url=url, duration_ms=duration_ms)
            return SandboxExecuteResponse(
                exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
                stdout="",
                stderr="Sandbox request timed out",
                duration_ms=duration_ms,
                error="TIMEOUT",
            )

        except httpx.ConnectError:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "sandbox_unavailable",
                url=url,
                reason="connection refused",
            )
            return SandboxExecuteResponse(
                exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
                stdout="",
                stderr="Sandbox executor is unavailable (connection refused)",
                duration_ms=duration_ms,
                error="SANDBOX_UNAVAILABLE",
            )

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("sandbox_client_unexpected_error", error=str(exc))
            return SandboxExecuteResponse(
                exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
                stdout="",
                stderr=f"Unexpected sandbox client error: {exc}",
                duration_ms=duration_ms,
                error="SANDBOX_UNAVAILABLE",
            )

    def health_check(self) -> bool:
        """Ping the sidecar health endpoint.

        Returns True if the sidecar is reachable and responds to /health.
        Used by Phase 3 to determine whether execution can proceed.
        """
        try:
            with httpx.Client(timeout=3) as client:
                response = client.get(
                    f"{self._base_url}/health",
                    headers={_AUTH_HEADER: self._secret},
                )
            return response.status_code == 200
        except Exception:
            return False
