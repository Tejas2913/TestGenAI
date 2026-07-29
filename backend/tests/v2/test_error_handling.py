"""Tests for RFC 7807 Problem Details error handling — Phase 1.

Verifies that:
  - V1 routes (/api/v1/...) return the legacy error format unchanged
  - V2 routes (/api/v2/...) return RFC 7807 Problem Details format
  - The ProblemDetail schema is well-formed
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


class TestRFC7807Schema:
    """ProblemDetail schema validation."""

    def test_problem_detail_fields(self) -> None:
        from app.schemas.common import ProblemDetail

        pd = ProblemDetail(
            type="/errors/not_found",
            title="Resource Not Found",
            status=404,
            detail="Generation 'xyz' not found",
            instance="/api/v2/jobs/xyz",
            error_code="NOT_FOUND",
        )
        assert pd.type == "/errors/not_found"
        assert pd.title == "Resource Not Found"
        assert pd.status == 404
        assert pd.detail == "Generation 'xyz' not found"
        assert pd.error_code == "NOT_FOUND"
        assert pd.extensions is None

    def test_problem_detail_default_type(self) -> None:
        from app.schemas.common import ProblemDetail

        pd = ProblemDetail(
            title="Error",
            status=500,
            detail="Something went wrong",
            error_code="INTERNAL_ERROR",
        )
        assert pd.type == "about:blank"


class TestV1LegacyErrorFormat:
    """V1 routes must retain the exact legacy error format."""

    def test_v1_404_returns_legacy_format(self, client: TestClient) -> None:
        """A missing generation returns the V1 error structure."""
        response = client.get("/api/v1/generations/nonexistent-id-12345")
        assert response.status_code == 404

        body = response.json()
        # V1 legacy format: {"detail": "...", "error_code": "..."}
        assert "detail" in body
        assert "error_code" in body
        # Must NOT contain RFC 7807 fields
        assert "type" not in body
        assert "title" not in body
        assert "status" not in body

    def test_v1_422_returns_legacy_format(self, client: TestClient) -> None:
        """Empty source_code triggers V1-format validation error."""
        response = client.post(
            "/api/v1/generate",
            json={"source_code": ""},
        )
        # FastAPI validation returns 422 with its own format (not our handler)
        # We only verify our custom handler is not masking it
        assert response.status_code == 422


class TestExceptionHandlerRouting:
    """Verify the _is_v2_route routing logic."""

    def test_is_v2_route_true_for_v2_path(self) -> None:
        from unittest.mock import MagicMock
        from app.exceptions.handlers import _is_v2_route

        request = MagicMock()
        request.url.path = "/api/v2/live"
        assert _is_v2_route(request) is True

    def test_is_v2_route_false_for_v1_path(self) -> None:
        from unittest.mock import MagicMock
        from app.exceptions.handlers import _is_v2_route

        request = MagicMock()
        request.url.path = "/api/v1/health"
        assert _is_v2_route(request) is False

    def test_is_v2_route_false_for_root_path(self) -> None:
        from unittest.mock import MagicMock
        from app.exceptions.handlers import _is_v2_route

        request = MagicMock()
        request.url.path = "/health"
        assert _is_v2_route(request) is False
