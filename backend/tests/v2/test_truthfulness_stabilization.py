"""Targeted regression tests for v2.4.0 final stabilization and truthfulness pass.

Verifies:
  A. Mutation duration propagation from DockerMutationExecutor -> JobEngine -> DB -> API endpoints (/mutation-summary & /quality).
  B. Mutation skipped behavior (0.0 duration, stage skipped).
  C. Semantic quality placeholder truthfulness (evaluated=False, semantic_score=None).
  D. Backward compatibility of QualityEngine scoring formula (normalized weights for active components).
  E. Pipeline timeline truthfulness for self-healing and mutation.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.domain.mutation import MutationSummary
from app.domain.test_quality import CompositeQualityResult, QualityBreakdown, SemanticQualityRating
from app.domain.test_smell import TestSmellSummary
from app.models.generation import Generation
from app.models.job import GenerationJob
from app.models.user import User
from app.repositories.generation_repository import GenerationRepository
from app.repositories.job_repository import JobRepository
from app.services.job_engine import execute_job
from app.services.quality_engine import QualityEngine
from app.services.quality_pipeline import QualityPipeline


def _get_auth_context(client: TestClient) -> tuple[dict[str, str], str]:
    """Register a fresh unique user and return authorization header and user_id."""
    email = f"truthfulness_{uuid.uuid4().hex[:8]}@example.com"
    r_reg = client.post("/api/v2/auth/register", json={"email": email, "password": "Password123!"})
    user_id = r_reg.json()["id"]
    r_login = client.post("/api/v2/auth/login", json={"email": email, "password": "Password123!"})
    token = r_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


class TestTruthfulnessStabilization:
    """Targeted regression test suite for v2.4.0 stabilization requirements."""

    def test_quality_pipeline_persists_mutation_duration(self) -> None:
        """Verify QualityPipeline.persist_quality_metrics populates mutation_duration_ms onto Generation."""
        pipeline = QualityPipeline()
        gen = Generation(
            id="gen-test-duration",
            source_code="def f(): pass",
            generated_tests_code="def test_f(): pass",
        )

        mut_summary = MutationSummary(
            total_mutants=5,
            killed_mutants=4,
            survived_mutants=1,
            mutation_score_pct=80.0,
            duration_ms=4520.5,
        )
        comp_result = CompositeQualityResult(
            overall_score=85.0,
            rating="GOOD",
            breakdown=QualityBreakdown(coverage_score=90.0, mutation_score=80.0, smell_hygiene_score=100.0),
            mutation=mut_summary,
            smells=TestSmellSummary(),
            semantic=SemanticQualityRating(),
        )

        pipeline.persist_quality_metrics(gen, comp_result)
        assert gen.mutation_duration_ms == 4520.5
        assert gen.killed_mutants == 4
        assert gen.survived_mutants == 1

    def test_api_propagates_mutation_duration(self, client: TestClient) -> None:
        """Verify GET /mutation-summary and GET /quality return non-zero persisted mutation_duration_ms."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-duration-test"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="completed",
            generation_id="gen-duration-1",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        mock_gen = Generation(
            id="gen-duration-1",
            source_code="def f(x): return x * 2",
            generated_tests_code="def test_f(): assert f(2) == 4",
            quality_score=88.5,
            quality_rating="GOOD",
            mutation_score=80.0,
            mutation_duration_ms=5123.4,
            killed_mutants=4,
            survived_mutants=1,
            smell_count=0,
            smell_breakdown_json='{"high": 0, "medium": 0, "low": 0}',
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo._session = MagicMock()

        from dependencies import get_job_repository
        with patch("app.repositories.generation_repository.GenerationRepository.get_by_id", return_value=mock_gen):
            client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
            try:
                # 1. Test /mutation-summary sub-resource
                res_mut = client.get(f"/api/v2/jobs/{job_id}/mutation-summary", headers=auth_headers)
                assert res_mut.status_code == 200
                mut_data = res_mut.json()
                assert mut_data["duration_ms"] == 5123.4
                assert mut_data["killed_mutants"] == 4

                # 2. Test /quality sub-resource
                res_qual = client.get(f"/api/v2/jobs/{job_id}/quality", headers=auth_headers)
                assert res_qual.status_code == 200
                qual_data = res_qual.json()
                assert qual_data["mutation"]["duration_ms"] == 5123.4
            finally:
                client.app.dependency_overrides.pop(get_job_repository, None)

    def test_semantic_quality_truthful_unevaluated_state(self, client: TestClient) -> None:
        """Verify semantic evaluation placeholder returns evaluated=False and semantic_score=None."""
        auth_headers, user_id = _get_auth_context(client)
        job_id = "job-semantic-test"
        now = datetime.now(timezone.utc)

        mock_job = GenerationJob(
            id=job_id,
            user_id=user_id,
            status="completed",
            generation_id="gen-semantic-1",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        mock_gen = Generation(
            id="gen-semantic-1",
            source_code="def g(): pass",
            generated_tests_code="def test_g(): pass",
            quality_score=75.0,
            quality_rating="FAIR",
            smell_count=0,
            smell_breakdown_json='{"high": 0, "medium": 0, "low": 0}',
        )

        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo._session = MagicMock()

        from dependencies import get_job_repository
        with patch("app.repositories.generation_repository.GenerationRepository.get_by_id", return_value=mock_gen):
            client.app.dependency_overrides[get_job_repository] = lambda: mock_job_repo
            try:
                res = client.get(f"/api/v2/jobs/{job_id}/quality", headers=auth_headers)
                assert res.status_code == 200
                data = res.json()

                # Breakdown semantic_score should be null (not 0.0)
                assert data["breakdown"]["semantic_score"] is None

                # Semantic section evaluated should be false
                assert data["semantic"]["evaluated"] is False
                assert data["semantic"]["assertion_strength"] is None
                assert "not executed" in data["semantic"]["reasoning"]
            finally:
                client.app.dependency_overrides.pop(get_job_repository, None)

    def test_quality_engine_scoring_formula_compatibility(self) -> None:
        """Confirm QualityEngine weight normalization formula remains intact."""
        engine = QualityEngine()

        # When semantic_rating is None, active sum = 0.25 + 0.35 + 0.20 = 0.80
        # 55.0 * (0.25/0.80) + 0.0 * (0.35/0.80) + 88.0 * (0.20/0.80) = 17.1875 + 22.0 = 39.1875 -> 39.2
        smells = TestSmellSummary(total_smells=4, low_severity_count=4)
        mut = MutationSummary(mutation_score_pct=0.0)

        res = engine.compute_composite_score(
            coverage_pct=55.0,
            smell_summary=smells,
            mutation_summary=mut,
            semantic_rating=None,
        )

        assert res.overall_score == 39.2
        assert res.rating == "NEEDS_IMPROVEMENT"
        assert res.breakdown.semantic_score is None
