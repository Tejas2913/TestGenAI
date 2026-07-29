"""Tests for V2.1 repositories — Phase 1.

Tests JobRepository, UserRepository, and ApiKeyRepository using the
in-memory test database provided by conftest.py.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.api_key import ApiKey
from app.models.job import JOB_STATUS_PENDING, GenerationJob
from app.models.user import User
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository


class TestJobRepository:
    """JobRepository CRUD operations."""

    def test_create_and_get_by_id(self, db_session) -> None:
        repo = JobRepository(db_session)
        job = repo.create({"id": str(uuid.uuid4()), "status": JOB_STATUS_PENDING})
        fetched = repo.get_by_id(job.id)
        assert fetched is not None
        assert fetched.id == job.id
        assert fetched.status == JOB_STATUS_PENDING

    def test_update_status(self, db_session) -> None:
        repo = JobRepository(db_session)
        job = repo.create({"id": str(uuid.uuid4()), "status": JOB_STATUS_PENDING})
        updated = repo.update(job.id, {"status": "processing"})
        assert updated is not None
        assert updated.status == "processing"

    def test_get_all_returns_jobs(self, db_session) -> None:
        repo = JobRepository(db_session)
        repo.create({"id": str(uuid.uuid4()), "status": JOB_STATUS_PENDING})
        repo.create({"id": str(uuid.uuid4()), "status": JOB_STATUS_PENDING})
        items, total = repo.get_all(offset=0, limit=10)
        assert total >= 2
        assert len(items) >= 2

    def test_get_by_id_nonexistent_returns_none(self, db_session) -> None:
        repo = JobRepository(db_session)
        result = repo.get_by_id("nonexistent-id")
        assert result is None


class TestUserRepository:
    """UserRepository CRUD + get_by_email."""

    def test_create_and_get_by_id(self, db_session) -> None:
        repo = UserRepository(db_session)
        user = repo.create({"id": str(uuid.uuid4()), "email": "test@example.com"})
        fetched = repo.get_by_id(user.id)
        assert fetched is not None
        assert fetched.email == "test@example.com"

    def test_get_by_email_found(self, db_session) -> None:
        repo = UserRepository(db_session)
        repo.create({"id": str(uuid.uuid4()), "email": "find@example.com"})
        result = repo.get_by_email("find@example.com")
        assert result is not None
        assert result.email == "find@example.com"

    def test_get_by_email_not_found(self, db_session) -> None:
        repo = UserRepository(db_session)
        result = repo.get_by_email("nobody@example.com")
        assert result is None

    def test_update_active_flag(self, db_session) -> None:
        repo = UserRepository(db_session)
        user = repo.create({"id": str(uuid.uuid4()), "email": "active@example.com"})
        updated = repo.update(user.id, {"is_active": False})
        assert updated is not None
        assert updated.is_active is False


class TestApiKeyRepository:
    """ApiKeyRepository CRUD + get_by_hash + get_keys_for_user."""

    def _make_key(self, db_session, user_id: str, hash_val: str, label: str = "key") -> ApiKey:
        repo = ApiKeyRepository(db_session)
        return repo.create(
            {"id": str(uuid.uuid4()), "user_id": user_id, "key_hash": hash_val, "label": label}
        )

    def test_create_and_get_by_id(self, db_session) -> None:
        repo = ApiKeyRepository(db_session)
        key = self._make_key(db_session, "user1", "d" * 64)
        fetched = repo.get_by_id(key.id)
        assert fetched is not None
        assert fetched.key_hash == "d" * 64

    def test_get_by_hash_returns_active_key(self, db_session) -> None:
        repo = ApiKeyRepository(db_session)
        self._make_key(db_session, "user1", "e" * 64)
        result = repo.get_by_hash("e" * 64)
        assert result is not None

    def test_get_by_hash_ignores_revoked_key(self, db_session) -> None:
        repo = ApiKeyRepository(db_session)
        revoke_time = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        key = repo.create(
            {
                "id": str(uuid.uuid4()),
                "user_id": "user2",
                "key_hash": "f" * 64,
                "revoked_at": revoke_time,
            }
        )
        result = repo.get_by_hash("f" * 64)
        assert result is None, "Revoked keys must not be returned by get_by_hash"

    def test_get_by_hash_missing_returns_none(self, db_session) -> None:
        repo = ApiKeyRepository(db_session)
        result = repo.get_by_hash("0" * 64)
        assert result is None

    def test_get_keys_for_user_returns_active_only(self, db_session) -> None:
        repo = ApiKeyRepository(db_session)
        user_id = str(uuid.uuid4())
        self._make_key(db_session, user_id, "a1" * 32, "key1")
        revoke_time = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        repo.create(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "key_hash": "a2" * 32,
                "revoked_at": revoke_time,
            }
        )
        keys = repo.get_keys_for_user(user_id)
        assert len(keys) == 1
        assert keys[0].key_hash == "a1" * 32
