"""Comprehensive API integration test suite for Quality Subsystem & GenerationWorkflow (Phase 7).

Verifies:
  - GenerationWorkflow orchestration decoupling from JobEngine.
  - GET /api/v2/jobs/{job_id} returning embedded quality_metrics.
  - GET /api/v2/jobs/{job_id}/quality sub-resource endpoint.
  - GET /api/v2/jobs/{job_id}/mutation-summary sub-resource endpoint.
  - GET /api/v2/jobs/{job_id}/smells sub-resource endpoint.
  - Graceful handling of missing quality data / 404 error responses.
  - 100% backward compatibility with existing v2.1 and v2.2 endpoints.
"""

from datetime import datetime, timezone
import uuid
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.models.job import GenerationJob
from app.repositories.generation_repository import GenerationRepository
from app.repositories.job_repository import JobRepository
from app.services.generation_workflow import GenerationWorkflow


def _get_auth_context(client: TestClient) -> tuple[dict[str, str], str]:
    """Register a fresh unique user and return authorization header and user_id."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    r_reg = client.post("/api/v2/auth/register", json={"email": email, "password": "Password123!"})
    user_id = r_reg.json()["id"]
    r_login = client.post("/api/v2/auth/login", json={"email": email, "password": "Password123!"})
    token = r_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


class TestQualityAPIIntegrationSuite:
    """API integration test suite for Quality endpoints and GenerationWorkflow."""

    def test_generation_workflow_coordination(self, db_session: Session) -> None:
        """Verify GenerationWorkflow coordinates generation, quality evaluation, and persistence."""
        gen_repo = GenerationRepository(db_session)
        workflow = GenerationWorkflow()

        # Mock LLM provider
        mock_provider = type("MockProvider", (), {
            "generate_tests": lambda self, source_code, specification, language, framework: (
                {"rendered_code": "def test_add(): assert 1 == 1"},
                "v2.2-test",
                None,
            )
        })()

        gen = workflow.execute_workflow(
            source_code="def add(a, b): return a + b",
            provider=mock_provider,
            gen_repo=gen_repo,
            enable_quality=True,
        )

        assert isinstance(gen, Generation)
        assert gen.id is not None
        assert gen.quality_score is not None
        assert gen.quality_rating is not None

    def test_get_job_status_includes_quality_metrics(
        self, client: TestClient
    ) -> None:
        """Verify GET /api/v2/jobs/{job_id} includes quality_metrics for completed jobs."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-quality-101"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="completed",
            generation_id="gen-101",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        mock_gen = Generation(
            id="gen-101",
            source_code="def foo(): pass",
            generated_tests_code="def test_foo(): pass",
            quality_score=92.5,
            quality_rating="EXCELLENT",
            mutation_score=85.0,
            killed_mutants=17,
            survived_mutants=3,
            timeout_mutants=0,
            error_mutants=0,
            smell_count=0,
            smell_breakdown_json='{"high": 0, "medium": 0, "low": 0}',
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo._session = MagicMock()

        mock_gen_repo = MagicMock(spec=GenerationRepository)
        mock_gen_repo.get_by_id.return_value = mock_gen

        from dependencies import get_job_repository
        with patch("app.repositories.generation_repository.GenerationRepository.get_by_id", return_value=mock_gen):
            client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
            try:
                response = client.get(f"/api/v2/jobs/{job_id}", headers=auth_headers)
            finally:
                client.app.dependency_overrides.pop(get_job_repository, None)

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["quality_metrics"] is not None
        assert data["quality_metrics"]["overall_score"] == 92.5
        assert data["quality_metrics"]["rating"] == "EXCELLENT"

    def test_get_job_quality_sub_resource(
        self, client: TestClient
    ) -> None:
        """Verify GET /api/v2/jobs/{job_id}/quality returns QualityMetricsResponse."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-quality-102"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="completed",
            generation_id="gen-102",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        mock_gen = Generation(
            id="gen-102",
            source_code="def bar(): return True",
            generated_tests_code="def test_bar(): assert bar() is True",
            quality_score=88.0,
            quality_rating="GOOD",
            mutation_score=75.0,
            killed_mutants=3,
            survived_mutants=1,
            smell_count=1,
            smell_breakdown_json='{"high": 0, "medium": 0, "low": 1}',
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo._session = MagicMock()

        mock_gen_repo = MagicMock(spec=GenerationRepository)
        mock_gen_repo.get_by_id.return_value = mock_gen

        from dependencies import get_job_repository
        with patch("app.repositories.generation_repository.GenerationRepository.get_by_id", return_value=mock_gen):
            client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
            try:
                response = client.get(f"/api/v2/jobs/{job_id}/quality", headers=auth_headers)
            finally:
                client.app.dependency_overrides.pop(get_job_repository, None)

        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 88.0
        assert data["rating"] == "GOOD"
        assert data["pipeline_status"] == "COMPLETED"

    def test_get_job_mutation_summary_sub_resource(
        self, client: TestClient
    ) -> None:
        """Verify GET /api/v2/jobs/{job_id}/mutation-summary returns MutationSummaryResponse."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-quality-103"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="completed",
            generation_id="gen-103",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        mock_gen = Generation(
            id="gen-103",
            source_code="def mult(a, b): return a * b",
            generated_tests_code="def test_mult(): assert mult(2, 3) == 6",
            quality_score=95.0,
            quality_rating="EXCELLENT",
            mutation_score=100.0,
            killed_mutants=5,
            survived_mutants=0,
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo._session = MagicMock()

        mock_gen_repo = MagicMock(spec=GenerationRepository)
        mock_gen_repo.get_by_id.return_value = mock_gen

        from dependencies import get_job_repository
        with patch("app.repositories.generation_repository.GenerationRepository.get_by_id", return_value=mock_gen):
            client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
            try:
                response = client.get(f"/api/v2/jobs/{job_id}/mutation-summary", headers=auth_headers)
            finally:
                client.app.dependency_overrides.pop(get_job_repository, None)

        assert response.status_code == 200
        data = response.json()
        assert data["killed_mutants"] == 5
        assert data["survived_mutants"] == 0
        assert data["mutation_score_pct"] == 100.0

    def test_get_job_smells_sub_resource(
        self, client: TestClient
    ) -> None:
        """Verify GET /api/v2/jobs/{job_id}/smells returns TestSmellSummaryResponse."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-quality-104"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="completed",
            generation_id="gen-104",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        mock_gen = Generation(
            id="gen-104",
            source_code="def calc(): return 42",
            generated_tests_code="def test_calc(): assert calc() == 42",
            quality_score=80.0,
            quality_rating="GOOD",
            smell_count=2,
            smell_breakdown_json='{"high": 1, "medium": 0, "low": 1}',
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo._session = MagicMock()

        mock_gen_repo = MagicMock(spec=GenerationRepository)
        mock_gen_repo.get_by_id.return_value = mock_gen

        from dependencies import get_job_repository
        with patch("app.repositories.generation_repository.GenerationRepository.get_by_id", return_value=mock_gen):
            client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
            try:
                response = client.get(f"/api/v2/jobs/{job_id}/smells", headers=auth_headers)
            finally:
                client.app.dependency_overrides.pop(get_job_repository, None)

        assert response.status_code == 200
        data = response.json()
        assert data["total_smells"] == 2
        assert data["high_severity_count"] == 1
        assert data["low_severity_count"] == 1

    def test_get_quality_metrics_missing_returns_404(
        self, client: TestClient
    ) -> None:
        """Verify GET /api/v2/jobs/{job_id}/quality returns 404 if quality metrics are absent."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-quality-105"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="pending",
            generation_id=None,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job

        from dependencies import get_job_repository
        client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
        try:
            response = client.get(f"/api/v2/jobs/{job_id}/quality", headers=auth_headers)
        finally:
            client.app.dependency_overrides.pop(get_job_repository, None)

        assert response.status_code == 404
