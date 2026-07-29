"""Shared Pydantic schemas used across multiple endpoints.

V1 schemas (frozen):
  ErrorResponse     — legacy error format returned by V1 exception handlers
  PaginatedResponse — generic paginated list wrapper

V2.1 additions:
  ProblemDetail — RFC 7807 Problem Details for V2 API error responses
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response returned by V1 exception handlers.

    V1.0 frozen contract — do not rename or remove fields.
    """

    detail: str = Field(description="Human-readable error message")
    error_code: str = Field(description="Machine-readable error code")


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response for V2 API endpoints.

    Fields:
        type    — URI identifying the problem type (relative or absolute)
        title   — short, human-readable summary of the problem
        status  — HTTP status code
        detail  — human-readable explanation specific to this occurrence
        instance — URI identifying this specific error occurrence (optional)
        error_code — machine-readable code for client error handling
        extensions — optional additional diagnostic fields (e.g. validation errors)
    """

    type: str = Field(
        default="about:blank",
        description="URI reference identifying the problem type",
    )
    title: str = Field(description="Short, human-readable problem summary")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation of this occurrence")
    instance: str | None = Field(
        default=None,
        description="URI identifying this specific error occurrence",
    )
    error_code: str = Field(description="Machine-readable application error code")
    extensions: dict[str, Any] | None = Field(
        default=None,
        description="Optional additional diagnostic fields",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Wrapper for paginated list responses."""

    items: list[T] = Field(description="Page of results")
    total: int = Field(description="Total number of records")
    page: int = Field(ge=1, description="Current page number")
    size: int = Field(ge=1, description="Items per page")
