"""FastAPI exception handlers for consistent error responses.

V1 routes (/api/v1/...) continue to receive the legacy error format:
    {"detail": "...", "error_code": "..."}

V2 routes (/api/v2/...) receive RFC 7807 Problem Details:
    {"type": "...", "title": "...", "status": ..., "detail": "...",
     "error_code": "...", "instance": "...", "extensions": null}

The routing decision is made by inspecting ``request.url.path``.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import AppException
from app.schemas.common import ProblemDetail

logger = structlog.get_logger()

# Map error_code to a short RFC 7807 title.
_ERROR_TITLES: dict[str, str] = {
    "NOT_FOUND": "Resource Not Found",
    "VALIDATION_ERROR": "Validation Error",
    "INPUT_TOO_LARGE": "Input Too Large",
    "DATABASE_ERROR": "Database Error",
    "INTERNAL_ERROR": "Internal Server Error",
    "LLM_ERROR": "LLM Provider Error",
    "LLM_TIMEOUT": "LLM Request Timeout",
    "LLM_RETRY_EXHAUSTED": "LLM Retries Exhausted",
    "PARSER_ERROR": "Response Parsing Error",
    "SANDBOX_ERROR": "Sandbox Execution Error",
    "AUTH_ERROR": "Authentication Error",
    "NETWORK_ERROR": "Network Error",
    "REVIEW_ERROR": "Review Error",
}


def _is_v2_route(request: Request) -> bool:
    """Return True when the request targets a V2 API route."""
    return request.url.path.startswith("/api/v2")


def _problem_detail(
    request: Request,
    exc_status: int,
    error_code: str,
    detail: str,
) -> JSONResponse:
    """Build and return an RFC 7807 Problem Details JSON response."""
    title = _ERROR_TITLES.get(error_code, "Error")
    body = ProblemDetail(
        type=f"/errors/{error_code.lower()}",
        title=title,
        status=exc_status,
        detail=detail,
        instance=request.url.path,
        error_code=error_code,
    )
    return JSONResponse(
        status_code=exc_status,
        content=body.model_dump(exclude_none=False),
        media_type="application/problem+json",
    )


def _legacy_error(status_code: int, detail: str, error_code: str) -> JSONResponse:
    """Return the V1 legacy error format (preserved for backward compatibility)."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_code": error_code},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach custom exception handlers to the FastAPI application.

    V1 routes keep the legacy JSON format.
    V2 routes receive RFC 7807 Problem Details responses.
    """

    @app.exception_handler(AppException)
    async def handle_app_exception(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """Handle all application-defined exceptions."""
        logger.warning(
            "app_exception",
            error_code=exc.error_code,
            detail=exc.detail,
            status_code=exc.status_code,
            path=request.url.path,
        )
        if _is_v2_route(request):
            return _problem_detail(
                request, exc.status_code, exc.error_code, exc.detail
            )
        return _legacy_error(exc.status_code, exc.detail, exc.error_code)

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unexpected exceptions."""
        logger.error(
            "unhandled_exception",
            error=str(exc),
            path=request.url.path,
            exc_info=True,
        )
        if _is_v2_route(request):
            return _problem_detail(
                request, 500, "INTERNAL_ERROR", "An unexpected error occurred"
            )
        return _legacy_error(500, "An unexpected error occurred", "INTERNAL_ERROR")
