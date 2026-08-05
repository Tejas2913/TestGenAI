"""Phase 3 tests — Async Job Engine & Self-Healing Pipeline.

Test coverage:
  TestJobRepository      — atomic_claim, save_checkpoint, get_jobs_by_status,
                           mark_orphaned_jobs, claim_for_retry
  TestJobLifecycle       — POST /jobs/generate, GET /jobs/{job_id}
  TestAtomicClaiming     — concurrent claim races; exactly-one-winner guarantee
  TestCheckpointPersistence — checkpoint saved and retrieved correctly
  TestStartupRecovery    — PROCESSING→ORPHANED→RETRYING on restart
  TestSelfHealing        — _is_repairable logic, repairable vs non-repairable
  TestJobEngine          — execute_job async wrapper
  TestJobFailurePaths    — FAILED transitions, error persistence
  TestSandboxIntegration — sandbox result flow through pipeline
"""

import json
import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.job import (
    CHECKPOINT_ANALYZED,
    CHECKPOINT_LLM_RESPONDED,
    CHECKPOINT_SANDBOX_TESTED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_ORPHANED,
    JOB_STATUS_PENDING,
    JOB_STATUS_PROCESSING,
    GenerationJob,
)
from app.repositories.job_repository import JobRepository
from app.services.job_engine import (
    MAX_REPAIR_ATTEMPTS,
    MAX_STARTUP_RETRIES,
    _is_repairable,
    _strip_markdown,
    startup_recovery,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(db_session, status: str = JOB_STATUS_PENDING, retry_count: int = 0) -> GenerationJob:
    """Create a GenerationJob fixture in the given status."""
    repo = JobRepository(db_session)
    return repo.create({
        "status": status,
        "user_id": str(uuid.uuid4()),
        "retry_count": retry_count,
    })


def _register_and_login(client: TestClient, email: str, pw: str) -> str:
    """Register a user and return an access token."""
    client.post("/api/v2/auth/register", json={"email": email, "password": pw})
    r = client.post("/api/v2/auth/login", json={"email": email, "password": pw})
    return r.json()["access_token"]


# ===========================================================================
# 1. JobRepository — atomic claiming and checkpoint methods
# ===========================================================================


class TestJobRepository:
    """Unit tests for Phase 3 JobRepository methods."""

    def test_atomic_claim_succeeds_when_pending(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)
        result = repo.atomic_claim(job.id)
        assert result is True

    def test_atomic_claim_transitions_to_processing(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)
        repo.atomic_claim(job.id)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.status == JOB_STATUS_PROCESSING

    def test_atomic_claim_fails_if_already_processing(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        result = repo.atomic_claim(job.id)
        assert result is False

    def test_atomic_claim_fails_for_nonexistent_job(self, db_session) -> None:
        repo = JobRepository(db_session)
        result = repo.atomic_claim(str(uuid.uuid4()))
        assert result is False

    def test_save_checkpoint_persists_name(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        repo.save_checkpoint(job.id, CHECKPOINT_ANALYZED)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.last_checkpoint == CHECKPOINT_ANALYZED

    def test_save_checkpoint_persists_payload(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        payload = json.dumps({"raw_response": "test output"})
        repo.save_checkpoint(job.id, CHECKPOINT_LLM_RESPONDED, payload)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.checkpoint_payload == payload
        assert job.last_checkpoint == CHECKPOINT_LLM_RESPONDED

    def test_save_checkpoint_updates_timestamp(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        repo.save_checkpoint(job.id, CHECKPOINT_ANALYZED)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.checkpoint_updated_at is not None

    def test_get_jobs_by_status_returns_matching(self, db_session) -> None:
        j1 = _make_job(db_session, JOB_STATUS_PENDING)
        j2 = _make_job(db_session, JOB_STATUS_PENDING)
        _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        pending = repo.get_jobs_by_status(JOB_STATUS_PENDING)
        ids = [j.id for j in pending]
        assert j1.id in ids
        assert j2.id in ids

    def test_get_jobs_by_status_empty(self, db_session) -> None:
        repo = JobRepository(db_session)
        result = repo.get_jobs_by_status(JOB_STATUS_ORPHANED)
        assert isinstance(result, list)

    def test_mark_orphaned_jobs_transitions_processing(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        repo.mark_orphaned_jobs()
        db_session.expire(job)
        db_session.refresh(job)
        assert job.status == JOB_STATUS_ORPHANED

    def test_mark_orphaned_jobs_leaves_pending_untouched(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)
        repo.mark_orphaned_jobs()
        db_session.expire(job)
        db_session.refresh(job)
        assert job.status == JOB_STATUS_PENDING

    def test_claim_for_retry_transitions_orphaned_to_pending(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_ORPHANED)
        repo = JobRepository(db_session)
        result = repo.claim_for_retry(job.id)
        assert result is True
        db_session.expire(job)
        db_session.refresh(job)
        assert job.status == JOB_STATUS_PENDING

    def test_claim_for_retry_increments_retry_count(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_ORPHANED, retry_count=0)
        repo = JobRepository(db_session)
        repo.claim_for_retry(job.id)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.retry_count == 1

    def test_claim_for_retry_fails_if_not_orphaned(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)
        result = repo.claim_for_retry(job.id)
        assert result is False


# ===========================================================================
# 2. Job lifecycle — HTTP endpoints
# ===========================================================================


class TestJobLifecycle:
    """Integration tests for POST /api/v2/jobs/generate and GET /api/v2/jobs/{job_id}."""

    def test_submit_job_returns_202(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        with patch("app.services.job_engine.execute_job"):
            response = client.post(
                "/api/v2/jobs/generate",
                json={"source_code": "def add(a, b): return a + b"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 202

    def test_submit_job_returns_job_id(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        with patch("app.api.v2.jobs.execute_job"):
            response = client.post(
                "/api/v2/jobs/generate",
                json={"source_code": "def add(a, b): return a + b"},
                headers={"Authorization": f"Bearer {token}"},
            )
        body = response.json()
        assert "job_id" in body
        assert len(body["job_id"]) == 36  # UUID format

    def test_submit_job_status_is_pending(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        with patch("app.api.v2.jobs.execute_job"):
            response = client.post(
                "/api/v2/jobs/generate",
                json={"source_code": "def add(a, b): return a + b"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.json()["status"] == "pending"

    def test_submit_job_requires_auth(self, client: TestClient) -> None:
        response = client.post(
            "/api/v2/jobs/generate",
            json={"source_code": "def add(a, b): return a + b"},
        )
        assert response.status_code == 401

    def test_submit_job_requires_source_code(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        response = client.post(
            "/api/v2/jobs/generate",
            json={"specification": "some spec only"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_get_job_returns_pending_status(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        with patch("app.api.v2.jobs.execute_job"):
            submit_r = client.post(
                "/api/v2/jobs/generate",
                json={"source_code": "def add(a, b): return a + b"},
                headers={"Authorization": f"Bearer {token}"},
            )
        job_id = submit_r.json()["job_id"]
        status_r = client.get(
            f"/api/v2/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_r.status_code == 200
        assert status_r.json()["job_id"] == job_id

    def test_get_nonexistent_job_returns_404(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        response = client.get(
            f"/api/v2/jobs/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_get_job_requires_auth(self, client: TestClient) -> None:
        response = client.get(f"/api/v2/jobs/{uuid.uuid4()}")
        assert response.status_code == 401

    def test_get_job_response_is_rfc7807_on_error(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        r = client.get(
            f"/api/v2/jobs/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = r.json()
        assert "type" in body
        assert "title" in body
        assert "status" in body

    def test_submit_job_response_has_message(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        with patch("app.api.v2.jobs.execute_job"):
            response = client.post(
                "/api/v2/jobs/generate",
                json={"source_code": "def add(a, b): return a + b"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert "message" in response.json()


# ===========================================================================
# 3. Atomic claiming — concurrent workers
# ===========================================================================


class TestAtomicClaiming:
    """Verify the exactly-one-winner guarantee under concurrent access."""

    def test_only_one_thread_can_claim(self, db_session) -> None:
        """Multiple sequential atomic_claim calls on the same session:
        the first succeeds; all subsequent return False.

        Note: SQLite in-memory with StaticPool serialises all access to a
        single connection, so thread-based concurrency tests are not
        meaningful here. The invariant is verified behaviourally via
        sequential calls — the SQL WHERE predicate guarantees exactly one
        winner regardless of concurrency level.
        """
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)

        # First claim must succeed
        first = repo.atomic_claim(job.id)
        assert first is True, "First claim must succeed"

        # All subsequent claims on the now-PROCESSING job must fail
        subsequent_results = [repo.atomic_claim(job.id) for _ in range(5)]
        assert all(r is False for r in subsequent_results), (
            "All subsequent claims must fail — job is already PROCESSING"
        )

    def test_claim_returns_false_when_job_is_completed(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_COMPLETED)
        repo = JobRepository(db_session)
        result = repo.atomic_claim(job.id)
        assert result is False

    def test_sequential_claims_second_fails(self, db_session) -> None:
        """Two sequential claim calls on the same session; only the first wins."""
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)

        r1 = repo.atomic_claim(job.id)
        r2 = repo.atomic_claim(job.id)  # job is now PROCESSING — must fail
        assert r1 is True
        assert r2 is False


# ===========================================================================
# 4. Checkpoint persistence
# ===========================================================================


class TestCheckpointPersistence:
    """Verify checkpoints are saved and retrievable for crash recovery."""

    def test_multiple_checkpoints_last_one_wins(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        repo.save_checkpoint(job.id, CHECKPOINT_ANALYZED)
        repo.save_checkpoint(job.id, CHECKPOINT_LLM_RESPONDED, '{"raw_response":"abc"}')
        db_session.expire(job)
        db_session.refresh(job)
        assert job.last_checkpoint == CHECKPOINT_LLM_RESPONDED
        assert "raw_response" in job.checkpoint_payload

    def test_checkpoint_payload_is_valid_json(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        payload = json.dumps({"raw_response": "some LLM output"})
        repo.save_checkpoint(job.id, CHECKPOINT_LLM_RESPONDED, payload)
        db_session.expire(job)
        db_session.refresh(job)
        parsed = json.loads(job.checkpoint_payload)
        assert parsed["raw_response"] == "some LLM output"

    def test_checkpoint_payload_can_be_none(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        repo.save_checkpoint(job.id, CHECKPOINT_ANALYZED, None)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.checkpoint_payload is None

    def test_checkpoint_sandbox_tested(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PROCESSING)
        repo = JobRepository(db_session)
        repo.save_checkpoint(job.id, CHECKPOINT_SANDBOX_TESTED)
        db_session.expire(job)
        db_session.refresh(job)
        assert job.last_checkpoint == CHECKPOINT_SANDBOX_TESTED


# ===========================================================================
# 5. Startup recovery
# ===========================================================================


class TestStartupRecovery:
    """Verify startup_recovery() correctly handles crashed jobs."""

    def test_processing_jobs_become_orphaned(self, db_session) -> None:
        # Plant a PROCESSING job to simulate a crash
        job = _make_job(db_session, JOB_STATUS_PROCESSING)

        # Run recovery using the same in-memory DB
        from app.db.session import SessionLocal
        with patch("app.services.job_engine.SessionLocal", return_value=db_session):
            # We need the repo to use our test session
            original_close = db_session.close
            db_session.close = lambda: None  # prevent close during recovery
            try:
                startup_recovery()
            finally:
                db_session.close = original_close

        db_session.expire(job)
        db_session.refresh(job)
        assert job.status in (JOB_STATUS_ORPHANED, JOB_STATUS_PENDING, JOB_STATUS_FAILED)

    def test_startup_recovery_returns_int(self) -> None:
        """startup_recovery() always returns an int (even 0)."""
        # Patch SessionLocal to return a session that has no PROCESSING jobs
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.mark_orphaned_jobs.return_value = []
        mock_repo.get_jobs_by_status.return_value = []

        with patch("app.services.job_engine.SessionLocal", return_value=mock_db):
            with patch("app.services.job_engine.JobRepository", return_value=mock_repo):
                result = startup_recovery()

        assert isinstance(result, int)
        assert result >= 0

    def test_startup_recovery_does_not_raise_on_db_error(self) -> None:
        """Recovery must not crash the application even if DB is unavailable."""
        # Patch the SessionLocal that job_engine imported at module level.
        # We import the engine module first to get the exact target path.
        import app.services.job_engine as engine_mod

        with patch.object(engine_mod, "SessionLocal", side_effect=Exception("DB down")):
            result = startup_recovery()

        assert result == 0

    def test_orphaned_job_with_no_retries_is_requeued(self) -> None:
        """An ORPHANED job with retry_count=0 should be transitioned to PENDING."""
        orphaned_job = MagicMock()
        orphaned_job.id = str(uuid.uuid4())
        orphaned_job.retry_count = 0

        mock_repo = MagicMock()
        mock_repo.mark_orphaned_jobs.return_value = [orphaned_job.id]
        mock_repo.get_jobs_by_status.return_value = [orphaned_job]
        mock_repo.claim_for_retry.return_value = True
        mock_db = MagicMock()
        mock_db.close = MagicMock()

        with patch("app.services.job_engine.SessionLocal", return_value=mock_db):
            with patch("app.services.job_engine.JobRepository", return_value=mock_repo):
                result = startup_recovery()

        mock_repo.claim_for_retry.assert_called_once_with(orphaned_job.id)
        assert result == 1

    def test_orphaned_job_exceeding_retry_limit_is_failed(self) -> None:
        """An ORPHANED job with retry_count >= MAX_STARTUP_RETRIES is marked FAILED."""
        orphaned_job = MagicMock()
        orphaned_job.id = str(uuid.uuid4())
        orphaned_job.retry_count = MAX_STARTUP_RETRIES  # at or beyond limit

        mock_repo = MagicMock()
        mock_repo.mark_orphaned_jobs.return_value = []
        mock_repo.get_jobs_by_status.return_value = [orphaned_job]
        mock_db = MagicMock()
        mock_db.close = MagicMock()

        with patch("app.services.job_engine.SessionLocal", return_value=mock_db):
            with patch("app.services.job_engine.JobRepository", return_value=mock_repo):
                startup_recovery()

        mock_repo.update.assert_called_once()
        call_kwargs = mock_repo.update.call_args
        assert call_kwargs[0][1]["status"] == JOB_STATUS_FAILED


# ===========================================================================
# 6. Self-healing — _is_repairable logic
# ===========================================================================


class TestSelfHealing:
    """Unit tests for the repair eligibility classifier."""

    def test_syntax_error_is_repairable(self) -> None:
        assert _is_repairable("SyntaxError: invalid syntax on line 5") is True

    def test_indentation_error_is_repairable(self) -> None:
        assert _is_repairable("IndentationError: unexpected indent") is True

    def test_module_not_found_is_repairable(self) -> None:
        assert _is_repairable("ModuleNotFoundError: No module named 'mylib'") is True

    def test_import_error_is_repairable(self) -> None:
        assert _is_repairable("ImportError: cannot import name 'foo'") is True

    def test_assertion_error_is_not_repairable(self) -> None:
        assert _is_repairable("AssertionError: expected 3 got 4") is False

    def test_timeout_is_not_repairable(self) -> None:
        assert _is_repairable("TimeoutExpired: command exceeded 5s") is False

    def test_sandbox_unavailable_is_not_repairable(self) -> None:
        assert _is_repairable("SANDBOX_UNAVAILABLE") is False

    def test_security_error_is_not_repairable(self) -> None:
        assert _is_repairable("security policy violation") is False

    def test_empty_stderr_is_not_repairable(self) -> None:
        assert _is_repairable("") is False

    def test_max_repair_attempts_is_3(self) -> None:
        assert MAX_REPAIR_ATTEMPTS == 3

    def test_max_startup_retries_is_1(self) -> None:
        assert MAX_STARTUP_RETRIES == 1


# ===========================================================================
# 7. _strip_markdown helper
# ===========================================================================


class TestStripMarkdown:
    """Verify the LLM fence-stripping utility."""

    def test_strips_python_fence(self) -> None:
        fenced = "```python\nprint('hello')\n```"
        assert _strip_markdown(fenced) == "print('hello')"

    def test_strips_generic_fence(self) -> None:
        fenced = "```\nsome code\n```"
        assert _strip_markdown(fenced) == "some code"

    def test_no_fence_unchanged(self) -> None:
        code = "def foo(): pass"
        assert _strip_markdown(code) == code

    def test_empty_string(self) -> None:
        assert _strip_markdown("") == ""


# ===========================================================================
# 8. Async execute_job wrapper
# ===========================================================================


class TestExecuteJob:
    """Verify the async execute_job wrapper delegates to _run_job_sync."""

    def test_execute_job_calls_run_sync(self) -> None:
        import asyncio

        job_id = str(uuid.uuid4())
        input_data = {"source_code": "def add(a,b): return a+b"}
        calls = []

        with patch(
            "app.services.job_engine._run_job_sync",
            side_effect=lambda jid, inp: calls.append((jid, inp)),
        ):
            asyncio.run(
                __import__("app.services.job_engine", fromlist=["execute_job"]).execute_job(
                    job_id, input_data
                )
            )

        assert len(calls) == 1
        assert calls[0][0] == job_id

    def test_execute_job_does_not_raise_on_worker_error(self) -> None:
        import asyncio
        from app.services.job_engine import execute_job

        job_id = str(uuid.uuid4())
        with patch(
            "app.services.job_engine._run_job_sync",
            side_effect=RuntimeError("worker exploded"),
        ):
            # Should not raise
            asyncio.run(execute_job(job_id, {}))


# ===========================================================================
# 9. Job failure path — error persistence
# ===========================================================================


class TestJobFailurePaths:
    """Verify error fields are persisted when jobs fail."""

    def test_failed_job_has_error_code(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)
        repo.update(job.id, {
            "status": JOB_STATUS_FAILED,
            "error_code": "LLM_ERROR",
            "error_detail": "LLM timed out",
        })
        db_session.expire(job)
        db_session.refresh(job)
        assert job.status == JOB_STATUS_FAILED
        assert job.error_code == "LLM_ERROR"
        assert job.error_detail == "LLM timed out"

    def test_completed_job_has_generation_id(self, db_session) -> None:
        job = _make_job(db_session, JOB_STATUS_PENDING)
        repo = JobRepository(db_session)
        gen_id = str(uuid.uuid4())
        repo.update(job.id, {
            "status": JOB_STATUS_COMPLETED,
            "generation_id": gen_id,
        })
        db_session.expire(job)
        db_session.refresh(job)
        assert job.status == JOB_STATUS_COMPLETED
        assert job.generation_id == gen_id

    def test_get_job_api_shows_error_on_failed(self, client: TestClient) -> None:
        uid = uuid.uuid4().hex[:8]
        token = _register_and_login(client, f"jobtest{uid}@example.com", "password123")
        # Submit a job
        with patch("app.api.v2.jobs.execute_job"):
            r = client.post(
                "/api/v2/jobs/generate",
                json={"source_code": "def add(a,b): return a+b"},
                headers={"Authorization": f"Bearer {token}"},
            )
        job_id = r.json()["job_id"]

        # Manually set it to FAILED via the DB (simulating engine failure)
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {
                "status": JOB_STATUS_FAILED,
                "error_code": "LLM_ERROR",
                "error_detail": "Provider unreachable",
            })
        finally:
            db.close()

        status_r = client.get(
            f"/api/v2/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = status_r.json()
        assert body["status"] == JOB_STATUS_FAILED
        assert body["error_code"] == "LLM_ERROR"


# ===========================================================================
# 10. Sandbox integration through the pipeline
# ===========================================================================


class TestSandboxIntegration:
    """Verify sandbox result flows through the pipeline correctly."""

    def test_run_job_sync_marks_completed_on_success(self) -> None:
        """_run_job_sync should transition job to COMPLETED on successful pipeline."""
        import app.services.job_engine as engine_mod
        from app.services.job_engine import _run_job_sync

        job_id = str(uuid.uuid4())

        mock_job_repo = MagicMock()
        mock_job_repo.atomic_claim.return_value = True
        mock_job_repo.update.return_value = None
        mock_job_repo.save_checkpoint.return_value = None

        mock_generation = MagicMock()
        mock_generation.id = str(uuid.uuid4())
        mock_generation.generated_tests_code = "def test_add(): assert add(1,2)==3"

        mock_service = MagicMock()
        mock_service.generate.return_value = mock_generation

        with (
            patch.object(engine_mod, "SessionLocal"),
            patch.object(engine_mod, "JobRepository", return_value=mock_job_repo),
            patch.object(engine_mod, "GenerationService", return_value=mock_service),
            patch.object(engine_mod, "LLMProviderRouter"),
            patch.object(engine_mod, "GenerationRepository"),
        ):
            _run_job_sync(job_id, {"source_code": "def add(a,b): return a+b"})

        # The last update call should set status=COMPLETED
        update_calls = mock_job_repo.update.call_args_list
        final_call = update_calls[-1]
        assert final_call[0][1]["status"] == JOB_STATUS_COMPLETED
        assert final_call[0][1]["generation_id"] == mock_generation.id

    def test_run_job_sync_marks_failed_on_exception(self) -> None:
        """_run_job_sync should transition job to FAILED when the pipeline raises."""
        import app.services.job_engine as engine_mod
        from app.services.job_engine import _run_job_sync

        job_id = str(uuid.uuid4())

        mock_job_repo = MagicMock()
        mock_job_repo.atomic_claim.return_value = True
        mock_job_repo.save_checkpoint.return_value = None

        mock_service = MagicMock()
        mock_service.generate.side_effect = RuntimeError("LLM exploded")

        with (
            patch.object(engine_mod, "SessionLocal"),
            patch.object(engine_mod, "JobRepository", return_value=mock_job_repo),
            patch.object(engine_mod, "GenerationService", return_value=mock_service),
            patch.object(engine_mod, "LLMProviderRouter"),
            patch.object(engine_mod, "GenerationRepository"),
        ):
            _run_job_sync(job_id, {"source_code": "def add(a,b): return a+b"})

        update_calls = mock_job_repo.update.call_args_list
        statuses = [c[0][1].get("status") for c in update_calls if "status" in c[0][1]]
        assert JOB_STATUS_FAILED in statuses

    def test_run_job_sync_skips_when_claim_fails(self) -> None:
        """If claim fails, _run_job_sync should exit without touching the DB."""
        import app.services.job_engine as engine_mod
        from app.services.job_engine import _run_job_sync

        job_id = str(uuid.uuid4())

        mock_job_repo = MagicMock()
        mock_job_repo.atomic_claim.return_value = False  # Another worker won

        with (
            patch.object(engine_mod, "SessionLocal"),
            patch.object(engine_mod, "JobRepository", return_value=mock_job_repo),
        ):
            _run_job_sync(job_id, {"source_code": "def add(a,b): return a+b"})

        # No update should have been called
        mock_job_repo.update.assert_not_called()
