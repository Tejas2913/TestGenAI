"""Tests for V2 health endpoints: /live and /ready."""

import pytest
from fastapi.testclient import TestClient


class TestLivenessEndpoint:
    """/api/v2/live — must respond instantly, never fail on I/O."""

    def test_live_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v2/live")
        assert response.status_code == 200

    def test_live_returns_status_alive(self, client: TestClient) -> None:
        body = client.get("/api/v2/live").json()
        assert body["status"] == "alive"

    def test_live_response_is_json(self, client: TestClient) -> None:
        response = client.get("/api/v2/live")
        assert "application/json" in response.headers["content-type"]

    def test_live_does_not_expose_database_field(self, client: TestClient) -> None:
        """Liveness must not include database connectivity — that belongs to /ready."""
        body = client.get("/api/v2/live").json()
        assert "database" not in body
        assert "ready" not in body


class TestReadinessEndpoint:
    """/api/v2/ready — must check DB connectivity and return 200 or 503."""

    def test_ready_returns_200_when_db_reachable(self, client: TestClient) -> None:
        """Monkeypatched check_database_connection returns True in test fixture."""
        response = client.get("/api/v2/ready")
        assert response.status_code == 200

    def test_ready_body_contains_ready_true(self, client: TestClient) -> None:
        body = client.get("/api/v2/ready").json()
        assert body["ready"] is True

    def test_ready_body_contains_database_true(self, client: TestClient) -> None:
        body = client.get("/api/v2/ready").json()
        assert body["database"] is True

    def test_ready_body_contains_configuration_true(self, client: TestClient) -> None:
        body = client.get("/api/v2/ready").json()
        assert body["configuration"] is True

    def test_ready_returns_503_when_db_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When DB is down /ready must return 503 not 200."""
        # Patch the reference that app.api.v2.health imports at call time.
        import app.api.v2.health as health_mod
        monkeypatch.setattr(health_mod, "check_database_connection", lambda: False)

        from fastapi.testclient import TestClient as TC
        from main import create_app

        app = create_app()
        with TC(app, raise_server_exceptions=True) as c:
            resp = c.get("/api/v2/ready")

        assert resp.status_code == 503
        body = resp.json()
        assert body["ready"] is False
        assert body["database"] is False

    def test_ready_does_not_call_llm(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Confirm no LLM call is made during readiness check."""
        llm_called = []

        import app.ai.providers.gemini_provider as gp

        def _fake_generate(*args, **kwargs):  # type: ignore[override]
            llm_called.append(True)
            raise AssertionError("LLM should not be called during /ready")

        monkeypatch.setattr(gp.GeminiProvider, "generate", _fake_generate, raising=False)

        client.get("/api/v2/ready")
        assert llm_called == [], "LLM was unexpectedly called during /ready"
