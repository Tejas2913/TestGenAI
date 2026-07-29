"""Unit tests for V2.1 ORM models — Phase 1.

Tests that GenerationJob, User, and ApiKey:
  - can be created with valid data
  - persist correctly to the in-memory test DB
  - enforce non-null constraints
  - default values are applied correctly
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.api_key import ApiKey
from app.models.job import (
    CHECKPOINT_ANALYZED,
    CHECKPOINT_LLM_RESPONDED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PENDING,
    JOB_STATUS_PROCESSING,
    GenerationJob,
)
from app.models.user import User


class TestGenerationJobModel:
    """GenerationJob ORM model tests."""

    def test_create_minimal_job(self, db_session) -> None:
        """A job can be created with only required fields."""
        job = GenerationJob(
            id=str(uuid.uuid4()),
            status=JOB_STATUS_PENDING,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.id is not None
        assert job.status == JOB_STATUS_PENDING
        assert job.retry_count == 0
        assert job.user_id is None
        assert job.generation_id is None
        assert job.last_checkpoint is None
        assert job.checkpoint_payload is None
        assert job.checkpoint_updated_at is None
        assert job.error_code is None
        assert job.error_detail is None

    def test_job_transitions_to_processing(self, db_session) -> None:
        job = GenerationJob(id=str(uuid.uuid4()), status=JOB_STATUS_PENDING)
        db_session.add(job)
        db_session.commit()

        job.status = JOB_STATUS_PROCESSING
        db_session.commit()
        db_session.refresh(job)

        assert job.status == JOB_STATUS_PROCESSING

    def test_job_checkpoint_fields_persist(self, db_session) -> None:
        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        job = GenerationJob(
            id=str(uuid.uuid4()),
            status=JOB_STATUS_PROCESSING,
            last_checkpoint=CHECKPOINT_ANALYZED,
            checkpoint_payload='{"ast": "..."}',
            checkpoint_updated_at=now,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.last_checkpoint == CHECKPOINT_ANALYZED
        assert job.checkpoint_payload == '{"ast": "..."}'

    def test_job_completed_with_generation_id(self, db_session) -> None:
        gen_id = str(uuid.uuid4())
        job = GenerationJob(
            id=str(uuid.uuid4()),
            status=JOB_STATUS_COMPLETED,
            generation_id=gen_id,
            last_checkpoint=CHECKPOINT_LLM_RESPONDED,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.generation_id == gen_id
        assert job.status == JOB_STATUS_COMPLETED

    def test_job_error_fields(self, db_session) -> None:
        job = GenerationJob(
            id=str(uuid.uuid4()),
            status="failed",
            error_code="LLM_TIMEOUT",
            error_detail="Request exceeded 60s timeout",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.error_code == "LLM_TIMEOUT"
        assert job.error_detail == "Request exceeded 60s timeout"

    def test_job_created_at_populated_automatically(self, db_session) -> None:
        job = GenerationJob(id=str(uuid.uuid4()), status=JOB_STATUS_PENDING)
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.created_at is not None
        assert job.updated_at is not None


class TestUserModel:
    """User ORM model tests."""

    def test_create_minimal_user(self, db_session) -> None:
        user = User(
            id=str(uuid.uuid4()),
            email="alice@example.com",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.is_active is True
        assert user.hashed_password is None
        assert user.org_id is None

    def test_email_uniqueness_enforced(self, db_session) -> None:
        email = "unique@example.com"
        u1 = User(id=str(uuid.uuid4()), email=email)
        u2 = User(id=str(uuid.uuid4()), email=email)
        db_session.add(u1)
        db_session.commit()
        db_session.add(u2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_soft_disable(self, db_session) -> None:
        user = User(id=str(uuid.uuid4()), email="bob@example.com", is_active=False)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.is_active is False

    def test_user_hashed_password_stored(self, db_session) -> None:
        user = User(
            id=str(uuid.uuid4()),
            email="charlie@example.com",
            hashed_password="$argon2id$...",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.hashed_password == "$argon2id$..."

    def test_user_created_at_auto(self, db_session) -> None:
        user = User(id=str(uuid.uuid4()), email="dave@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.created_at is not None


class TestApiKeyModel:
    """ApiKey ORM model tests."""

    def test_create_api_key(self, db_session) -> None:
        user_id = str(uuid.uuid4())
        key = ApiKey(
            id=str(uuid.uuid4()),
            user_id=user_id,
            key_hash="a" * 64,
            label="CI pipeline",
        )
        db_session.add(key)
        db_session.commit()
        db_session.refresh(key)

        assert key.user_id == user_id
        assert key.key_hash == "a" * 64
        assert key.label == "CI pipeline"
        assert key.revoked_at is None

    def test_key_hash_must_be_unique(self, db_session) -> None:
        hash_val = "b" * 64
        k1 = ApiKey(id=str(uuid.uuid4()), user_id="u1", key_hash=hash_val)
        k2 = ApiKey(id=str(uuid.uuid4()), user_id="u2", key_hash=hash_val)
        db_session.add(k1)
        db_session.commit()
        db_session.add(k2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestGenerationCoverageFields:
    """Generation ORM coverage fields persistence tests."""

    def test_generation_persists_coverage_fields(self, db_session) -> None:
        from app.models.generation import Generation

        gen = Generation(
            id=str(uuid.uuid4()),
            source_code="def add(a, b): return a + b",
            coverage_line_pct=100.0,
            coverage_branch_pct=100.0,
            coverage_total_statements=2,
            coverage_covered_statements=2,
            coverage_missing_statements=0,
        )
        db_session.add(gen)
        db_session.commit()
        db_session.refresh(gen)

        assert gen.coverage_line_pct == 100.0
        assert gen.coverage_branch_pct == 100.0
        assert gen.coverage_total_statements == 2
        assert gen.coverage_covered_statements == 2
        assert gen.coverage_missing_statements == 0

    def test_generation_coverage_fields_default_to_none(self, db_session) -> None:
        from app.models.generation import Generation

        gen = Generation(
            id=str(uuid.uuid4()),
            source_code="def sub(a, b): return a - b",
        )
        db_session.add(gen)
        db_session.commit()
        db_session.refresh(gen)

        assert gen.coverage_line_pct is None
        assert gen.coverage_branch_pct is None
        assert gen.coverage_total_statements is None
        assert gen.coverage_covered_statements is None
        assert gen.coverage_missing_statements is None
