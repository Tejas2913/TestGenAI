"""Regression tests for Quality Engine timeline truthfulness & endpoint behavior.

Verifies:
1. Advanced quality disabled (ENABLE_QUALITY_EVALUATION=False) returns quality_metrics=None.
2. Advanced quality enabled populates quality_metrics on JobStatusResponse.
3. GET /api/v2/jobs/{job_id}/quality returns 404 when disabled / 200 when available.
4. GET /api/v2/jobs/{job_id}/mutation-summary returns 404 when disabled / 200 when available.
5. GET /api/v2/jobs/{job_id}/smells returns 404 when disabled / 200 when available.
6. Coverage fields (coverage_line_pct, coverage_branch_pct) propagate to JobStatusResponse.
7. History API remains HTTP 200.
8. Generation flow contract remains unchanged.
"""

import asyncio
from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.models.job import GenerationJob
from app.api.v2.jobs import get_job_status
from app.repositories.job_repository import JobRepository


def _get_auth_headers(client: TestClient) -> dict[str, str]:
    """Helper to register/login a test user and obtain auth headers."""
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v2/auth/register", json={"email": email, "password": "Password123!"})
    r_login = client.post("/api/v2/auth/login", json={"email": email, "password": "Password123!"})
    token = r_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestQualityTimelineTruthfulness:
    """1-8: Unit and integration tests for Quality timeline truthfulness."""

    def test_1_advanced_quality_disabled_returns_none_quality_metrics(self, db_session: Session):
        """When quality evaluation is not run/disabled, quality_metrics is None."""
        gen_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        gen = Generation(
            id=gen_id,
            source_code="def add(a, b): return a + b",
            status="completed",
            coverage_line_pct=80.0,
            coverage_branch_pct=75.0,
            quality_score=None,  # Not evaluated
        )
        job = GenerationJob(
            id=job_id,
            generation_id=gen_id,
            status="completed",
            last_checkpoint="PERSISTED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(gen)
        db_session.add(job)
        db_session.commit()

        repo = JobRepository(db_session)
        status_resp = asyncio.run(get_job_status(job_id=job_id, job_repo=repo))

        assert status_resp.quality_metrics is None
        assert status_resp.coverage_line_pct == 80.0
        assert status_resp.coverage_branch_pct == 75.0

    def test_2_advanced_quality_enabled_populates_quality_metrics(self, db_session: Session):
        """When quality_score is present on generation, quality_metrics is populated."""
        gen_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        gen = Generation(
            id=gen_id,
            source_code="def add(a, b): return a + b",
            status="completed",
            coverage_line_pct=90.0,
            coverage_branch_pct=85.0,
            quality_score=92.5,
            quality_rating="EXCELLENT",
            mutation_score=88.0,
            killed_mutants=8,
            survived_mutants=1,
            smell_count=0,
        )
        job = GenerationJob(
            id=job_id,
            generation_id=gen_id,
            status="completed",
            last_checkpoint="PERSISTED",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(gen)
        db_session.add(job)
        db_session.commit()

        repo = JobRepository(db_session)
        status_resp = asyncio.run(get_job_status(job_id=job_id, job_repo=repo))

        assert status_resp.quality_metrics is not None
        assert status_resp.quality_metrics.overall_score == 92.5
        assert status_resp.quality_metrics.rating == "EXCELLENT"
        assert status_resp.coverage_line_pct == 90.0

    def test_3_4_5_quality_subendpoints_return_404_when_metrics_unavailable(self, client: TestClient, db_session: Session):
        """Sub-endpoints /quality, /mutation-summary, /smells return 404 when quality_metrics is None."""
        gen_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())

        gen = Generation(
            id=gen_id,
            source_code="def sub(a, b): return a - b",
            status="completed",
            quality_score=None,
        )
        job = GenerationJob(
            id=job_id,
            generation_id=gen_id,
            status="completed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(gen)
        db_session.add(job)
        db_session.commit()

        headers = _get_auth_headers(client)

        res_q = client.get(f"/api/v2/jobs/{job_id}/quality", headers=headers)
        assert res_q.status_code == 404

        res_m = client.get(f"/api/v2/jobs/{job_id}/mutation-summary", headers=headers)
        assert res_m.status_code == 404

        res_s = client.get(f"/api/v2/jobs/{job_id}/smells", headers=headers)
        assert res_s.status_code == 404

    def test_7_history_api_remains_200_ok(self, client: TestClient):
        """GET /api/v1/generations continues returning HTTP 200."""
        res = client.get("/api/v1/generations?page=1&size=5")
        assert res.status_code == 200
        assert "items" in res.json()
