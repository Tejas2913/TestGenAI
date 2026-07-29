"""Custom exception classes for the application.

V1.0 Error Code Registry — frozen baseline.

All error codes follow SCREAMING_SNAKE_CASE convention.
HTTP status codes are NOT changed by subclassing — only error_code changes.

V1 codes:
  INTERNAL_ERROR      — unhandled / unexpected error (500)
  NOT_FOUND           — resource does not exist (404)
  VALIDATION_ERROR    — request data fails validation (422)
  INPUT_TOO_LARGE     — input exceeds configured size limit (422)
  DATABASE_ERROR      — database operation failure (500)
  LLM_ERROR           — base LLM provider error (502)
  LLM_TIMEOUT         — LLM request exceeded timeout (502)
  LLM_RETRY_EXHAUSTED — all LLM retry attempts failed (502)
  PARSER_ERROR        — LLM response failed structured parsing (502)

Reserved for V2 (not yet raised anywhere):
  SANDBOX_ERROR       — test execution sandbox failure
  REVIEW_ERROR        — LLM review pass failure
  AUTH_ERROR          — authentication / authorization failure
  NETWORK_ERROR       — upstream network connectivity failure
"""


class AppException(Exception):
    """Base exception for all application-level errors."""

    def __init__(
        self,
        detail: str = "An unexpected error occurred",
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
    ) -> None:
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(detail)


class NotFoundException(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(detail=detail, error_code="NOT_FOUND", status_code=404)


class ValidationException(AppException):
    """Raised when request data fails validation."""

    def __init__(self, detail: str = "Validation error") -> None:
        super().__init__(detail=detail, error_code="VALIDATION_ERROR", status_code=422)


class DatabaseException(AppException):
    """Raised when a database operation fails."""

    def __init__(self, detail: str = "Database error") -> None:
        super().__init__(detail=detail, error_code="DATABASE_ERROR", status_code=500)


class InputTooLargeException(AppException):
    """Raised when input exceeds configured size limits."""

    def __init__(self, detail: str = "Input exceeds maximum allowed size") -> None:
        super().__init__(
            detail=detail, error_code="INPUT_TOO_LARGE", status_code=422
        )


# ---------------------------------------------------------------------------
# LLM-specific exceptions
# ---------------------------------------------------------------------------


class LLMException(AppException):
    """Base exception for all LLM provider errors."""

    def __init__(self, detail: str = "LLM provider error") -> None:
        super().__init__(detail=detail, error_code="LLM_ERROR", status_code=502)


class LLMTimeoutException(LLMException):
    """Raised when an LLM request exceeds the configured timeout."""

    def __init__(self, detail: str = "LLM request timed out") -> None:
        super().__init__(detail=detail)
        self.error_code = "LLM_TIMEOUT"


class LLMRetryExhaustedException(LLMException):
    """Raised when all retry attempts for an LLM request have been exhausted."""

    def __init__(
        self,
        detail: str = "LLM request failed after all retries",
        attempts: int = 0,
    ) -> None:
        super().__init__(detail=detail)
        self.error_code = "LLM_RETRY_EXHAUSTED"
        self.attempts = attempts


# ---------------------------------------------------------------------------
# Parser exceptions
# ---------------------------------------------------------------------------


class ParserException(AppException):
    """Raised when the LLM response cannot be parsed into the expected structure.

    This is distinct from LLMException — the LLM call succeeded but the
    response payload was malformed or did not match the required JSON schema.
    """

    def __init__(self, detail: str = "Failed to parse LLM response") -> None:
        super().__init__(detail=detail, error_code="PARSER_ERROR", status_code=502)


# ---------------------------------------------------------------------------
# V2 reserved exception stubs — NOT raised by any V1 code.
# Defined here so V2 can import and raise them without modifying this file.
# ---------------------------------------------------------------------------


class SandboxException(AppException):
    """Reserved for V2: raised when the test execution sandbox fails."""

    def __init__(self, detail: str = "Test sandbox execution failed") -> None:
        super().__init__(detail=detail, error_code="SANDBOX_ERROR", status_code=500)


class ReviewException(AppException):
    """Reserved for V2: raised when the LLM review pass fails."""

    def __init__(self, detail: str = "Test review pass failed") -> None:
        super().__init__(detail=detail, error_code="REVIEW_ERROR", status_code=502)


class AuthException(AppException):
    """Reserved for V2: raised when authentication or authorization fails."""

    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(detail=detail, error_code="AUTH_ERROR", status_code=401)


class NetworkException(AppException):
    """Reserved for V2: raised when an upstream network request fails."""

    def __init__(self, detail: str = "Network connectivity error") -> None:
        super().__init__(detail=detail, error_code="NETWORK_ERROR", status_code=502)
