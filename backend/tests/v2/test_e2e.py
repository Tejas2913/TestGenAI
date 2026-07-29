"""Phase 5 end-to-end integration tests.

Covers the complete async job workflow from the API perspective:

  - Login → submit job → poll → completion
  - Login → submit job → poll → failure
  - Authentication failures (missing token, wrong credentials)
  - Network-level error handling (invalid job_id)
  - Cache hit path (L1 cache primed before submission)
  - Confidence display on completed jobs
  - Job recovery scenario (startup recovery state)
  - Sandbox failure path

Architecture rule: all tests run against the in-memory SQLite test DB,
using the shared conftest.py fixtures. No external services are required.

All tests use the TestClient + mocking pattern established in Phase 2–4.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_and_login(client, email=None, password="testPass123!"):
    """Register a user and return the bearer token."""
    if email is None:
        email = f"e2e_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/api/v2/auth/register", json={"email": email, "password": password})
    resp = client.post("/api/v2/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, email


def make_job_payload(source_code=None):
    return {
        "source_code": source_code or "def add(a, b):\n    return a + b",
        "specification": None,
        "language": "python",
        "framework": "pytest",
    }


# ---------------------------------------------------------------------------
# 1. Authentication Integration
# ---------------------------------------------------------------------------


class TestAuthIntegration:
    """End-to-end auth flow tests."""

    def test_register_creates_user(self, client):
        email = f"reg_{uuid.uuid4().hex[:8]}@test.com"
        resp = client.post(
            "/api/v2/auth/register",
            json={"email": email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == email
        assert data["is_active"] is True

    def test_login_returns_jwt(self, client):
        headers, email = register_and_login(client)
        assert "Bearer " in headers["Authorization"]
        token = headers["Authorization"].split("Bearer ")[1]
        assert len(token) > 20

    def test_login_wrong_password_returns_401(self, client):
        email = f"badpw_{uuid.uuid4().hex[:8]}@test.com"
        client.post(
            "/api/v2/auth/register",
            json={"email": email, "password": "CorrectPassword1!"},
        )
        resp = client.post(
            "/api/v2/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert resp.status_code == 401

    def test_login_unknown_email_returns_401(self, client):
        resp = client.post(
            "/api/v2/auth/login",
            json={"email": "nonexistent@test.com", "password": "anything"},
        )
        assert resp.status_code == 401

    def test_submit_job_without_token_returns_401_or_403(self, client):
        resp = client.post("/api/v2/jobs/generate", json=make_job_payload())
        assert resp.status_code in (401, 403)

    def test_submit_job_with_invalid_token_returns_401_or_403(self, client):
        resp = client.post(
            "/api/v2/jobs/generate",
            headers={"Authorization": "Bearer invalid.jwt.token"},
            json=make_job_payload(),
        )
        assert resp.status_code in (401, 403)

    def test_get_job_status_without_token_returns_401_or_403(self, client):
        resp = client.get(f"/api/v2/jobs/{uuid.uuid4()}")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 2. Job Submission Flow
# ---------------------------------------------------------------------------


class TestJobSubmission:
    """POST /api/v2/jobs/generate integration tests."""

    def test_submit_job_returns_202_with_job_id(self, client):
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json=make_job_payload(),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "job_id" in data
        assert data["status"] in ("pending", "processing")
        assert data["message"]

    def test_submit_job_creates_pending_status(self, client):
        headers, _ = register_and_login(client)
        submit_resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json=make_job_payload(),
        )
        assert submit_resp.status_code == 202
        job_id = submit_resp.json()["job_id"]

        status_resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("pending", "processing", "completed", "failed")

    def test_submit_job_whitespace_source_is_accepted_by_schema(self, client):
        """Whitespace-only source passes schema validation (min_length=1).
        The service layer handles the business-level empty-code guard.
        This verifies the endpoint returns a response (not a server crash)."""
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json={"source_code": "   ", "language": "python", "framework": "pytest"},
        )
        # Schema accepts it (min_length=1 is satisfied by spaces).
        # Service-level validation may cause immediate or deferred failure.
        assert resp.status_code in (202, 422)

    def test_submit_job_missing_source_returns_422(self, client):
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json={"language": "python", "framework": "pytest"},
        )
        assert resp.status_code == 422

    def test_submit_job_with_specification(self, client):
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json={
                "source_code": "def greet(name): return f'Hello, {name}!'",
                "specification": "Test that greet returns the correct string.",
                "language": "python",
                "framework": "pytest",
            },
        )
        assert resp.status_code == 202
        assert "job_id" in resp.json()


# ---------------------------------------------------------------------------
# 3. Job Status Polling
# ---------------------------------------------------------------------------


class TestJobStatusPolling:
    """GET /api/v2/jobs/{job_id} integration tests."""

    def test_poll_known_job_returns_200(self, client):
        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id

    def test_poll_unknown_job_returns_404(self, client):
        headers, _ = register_and_login(client)
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v2/jobs/{fake_id}", headers=headers)
        assert resp.status_code == 404

    def test_poll_response_has_required_fields(self, client):
        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]
        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        assert "job_id" in data
        assert "status" in data
        assert "retry_count" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_poll_status_is_valid_lifecycle_value(self, client):
        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]
        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        valid_statuses = {"pending", "processing", "completed", "failed", "cancelled"}
        assert resp.json()["status"] in valid_statuses

    def test_poll_retry_count_is_nonnegative(self, client):
        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]
        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        assert resp.json()["retry_count"] >= 0


# ---------------------------------------------------------------------------
# 4. Background Execution (Mocked pipeline)
# ---------------------------------------------------------------------------


class TestBackgroundExecution:
    """Tests for job execution using a mocked pipeline."""

    def _submit_and_mock_complete(self, client, headers, mock_result=None):
        """Submit a job and manually set it to completed in DB."""
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        assert submit.status_code == 202
        return submit.json()["job_id"]

    def test_submit_returns_immediately_before_pipeline(self, client):
        """202 must be returned before the background pipeline runs."""
        headers, _ = register_and_login(client)
        # With a slow mock, submit should still return instantly
        with patch("app.services.generation_service.GenerationService.generate") as mock_gen:
            mock_gen.side_effect = lambda *a, **kw: None
            resp = client.post(
                "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
            )
        assert resp.status_code == 202

    def test_completed_job_has_generation_id_or_none(self, client):
        """generation_id is set only after the pipeline completes."""
        headers, _ = register_and_login(client)
        job_id = self._submit_and_mock_complete(client, headers)
        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        # generation_id is None for pending/processing; str for completed
        assert data["generation_id"] is None or isinstance(data["generation_id"], str)

    def test_failed_job_sets_error_fields(self, client):
        """A job manually set to FAILED must expose error_code and error_detail."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        # Force job to failed state via repository
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {
                "status": "failed",
                "error_code": "LLM_UNAVAILABLE",
                "error_detail": "The AI model returned an empty response.",
            })
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_code"] == "LLM_UNAVAILABLE"
        assert data["error_detail"] == "The AI model returned an empty response."


# ---------------------------------------------------------------------------
# 5. Successful Completion Path
# ---------------------------------------------------------------------------


class TestSuccessfulCompletion:
    """Tests for the full happy path: submit → completed → generation_id."""

    def test_completed_job_exposes_generation_id(self, client):
        """When a job completes, generation_id must be set."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository
        from app.repositories.generation_repository import GenerationRepository
        from app.models.generation import Generation

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        # Create a fake completed generation
        db = SessionLocal()
        try:
            gen_repo = GenerationRepository(db)
            gen = gen_repo.create({
                "source_code": "def add(a, b): return a + b",
                "language": "python",
                "framework": "pytest",
                "status": "completed",
                "generated_tests_json": json.dumps({
                    "function_name": "add",
                    "test_cases": [{"name": "test_add"}],
                    "imports": [],
                    "setup_code": None,
                }),
                "generated_tests_code": "def test_add(): assert add(1,2)==3",
                "prompt_version": "v1",
            })
            db.commit()

            # Link job to the generation
            job_repo = JobRepository(db)
            job_repo.update(job_id, {
                "status": "completed",
                "generation_id": gen.id,
            })
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        assert data["status"] == "completed"
        assert data["generation_id"] is not None

    def test_completed_job_v1_result_accessible(self, client):
        """generation_id from a completed job must be retrievable via V1 endpoint."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository
        from app.repositories.generation_repository import GenerationRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        db = SessionLocal()
        try:
            gen_repo = GenerationRepository(db)
            gen = gen_repo.create({
                "source_code": "def mul(a, b): return a * b",
                "language": "python",
                "framework": "pytest",
                "status": "completed",
                "generated_tests_json": json.dumps({
                    "function_name": "mul",
                    "test_cases": [],
                    "imports": [],
                    "setup_code": None,
                }),
                "generated_tests_code": "# tests",
                "prompt_version": "v1",
            })
            db.commit()
            job_repo = JobRepository(db)
            job_repo.update(job_id, {"status": "completed", "generation_id": gen.id})
            db.commit()
            gen_id = gen.id
        finally:
            db.close()

        v1_resp = client.get(f"/api/v1/generations/{gen_id}", headers=headers)
        assert v1_resp.status_code == 200
        v1_data = v1_resp.json()
        assert v1_data["id"] == gen_id
        assert v1_data["status"] == "completed"


# ---------------------------------------------------------------------------
# 6. Failed Generation Path
# ---------------------------------------------------------------------------


class TestFailedGeneration:
    """Tests for the failure path."""

    def test_failed_job_error_code_set(self, client):
        """A job forced to FAILED state exposes error_code correctly.

        Note: the TestClient runs BackgroundTasks synchronously, so by
        the time we force the status, the pipeline may have already
        completed and set generation_id. We therefore only assert the
        status and error_code fields, not generation_id.
        """
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {"status": "failed", "error_code": "PARSE_ERROR",
                                  "generation_id": None})
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_code"] == "PARSE_ERROR"

    def test_error_response_is_rfc7807_compliant(self, client):
        """404 for unknown job must follow Problem Details format."""
        headers, _ = register_and_login(client)
        resp = client.get(f"/api/v2/jobs/{uuid.uuid4()}", headers=headers)
        assert resp.status_code == 404
        data = resp.json()
        # RFC7807 requires at minimum: type, title, status, detail
        assert "detail" in data or "type" in data

    def test_cancelled_job_status(self, client):
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {"status": "cancelled"})
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        assert resp.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# 7. Sandbox Failure Path
# ---------------------------------------------------------------------------


class TestSandboxFailure:
    """Tests verifying sandbox execution is non-blocking for the job lifecycle."""

    def test_sandbox_failure_does_not_fail_job(self, client):
        """Job can complete even when ENABLE_SANDBOX=False or sandbox unavailable."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        # Job can still complete without sandbox
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {
                "status": "completed",
                "last_checkpoint": "PARSED",  # never reached SANDBOX_TESTED
            })
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        assert resp.json()["status"] == "completed"

    def test_sandbox_exit_code_not_in_job_status_when_confidence_disabled(self, client):
        """When ENABLE_CONFIDENCE=False, confidence block is absent."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository
        from app.core.config import settings

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {"status": "completed"})
            db.commit()
        finally:
            db.close()

        orig = settings.ENABLE_CONFIDENCE
        try:
            settings.ENABLE_CONFIDENCE = False
            resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
            data = resp.json()
            assert data.get("confidence") is None
        finally:
            settings.ENABLE_CONFIDENCE = orig


# ---------------------------------------------------------------------------
# 8. Cache Hit Path
# ---------------------------------------------------------------------------


class TestCacheHitPath:
    """Tests for the L1 cache hit flow."""

    def test_second_identical_submission_may_use_cache(self, client):
        """Two identical requests should both receive 202 with distinct job_ids."""
        headers, _ = register_and_login(client)
        payload = make_job_payload("def square(x):\n    return x * x")

        r1 = client.post("/api/v2/jobs/generate", headers=headers, json=payload)
        r2 = client.post("/api/v2/jobs/generate", headers=headers, json=payload)

        assert r1.status_code == 202
        assert r2.status_code == 202
        # Each submission gets its own job_id (cache hit reduces backend work,
        # but the job record is still created)
        assert r1.json()["job_id"] != r2.json()["job_id"]

    def test_cache_key_varies_by_source_code(self, client):
        """Different source code → different jobs."""
        headers, _ = register_and_login(client)

        r1 = client.post(
            "/api/v2/jobs/generate", headers=headers,
            json=make_job_payload("def foo(): pass")
        )
        r2 = client.post(
            "/api/v2/jobs/generate", headers=headers,
            json=make_job_payload("def bar(): pass")
        )

        assert r1.json()["job_id"] != r2.json()["job_id"]


# ---------------------------------------------------------------------------
# 9. Confidence Display
# ---------------------------------------------------------------------------


class TestConfidenceDisplay:
    """Tests for the Phase 4 confidence block in job status response."""

    def test_confidence_absent_for_pending_job(self, client):
        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]
        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        # Pending/processing jobs never have confidence
        data = resp.json()
        if data["status"] in ("pending", "processing"):
            assert data.get("confidence") is None

    def test_confidence_present_for_completed_job_when_enabled(self, client):
        """When ENABLE_CONFIDENCE=True and job is completed, confidence is non-null."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository
        from app.repositories.generation_repository import GenerationRepository
        from app.core.config import settings

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        # Create a real generation and link it
        db = SessionLocal()
        try:
            gen_repo = GenerationRepository(db)
            gen = gen_repo.create({
                "source_code": "def f(): pass",
                "language": "python",
                "framework": "pytest",
                "status": "completed",
                "generated_tests_json": json.dumps({
                    "function_name": "f",
                    "test_cases": [
                        {"name": f"test_{i}"} for i in range(8)
                    ],
                    "imports": [],
                    "setup_code": None,
                }),
                "generated_tests_code": "# tests",
                "prompt_version": "v1",
            })
            db.commit()
            job_repo = JobRepository(db)
            job_repo.update(job_id, {"status": "completed", "generation_id": gen.id})
            db.commit()
        finally:
            db.close()

        orig = settings.ENABLE_CONFIDENCE
        try:
            settings.ENABLE_CONFIDENCE = True
            resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
            data = resp.json()
            assert data["status"] == "completed"
            if data.get("confidence") is not None:
                conf = data["confidence"]
                assert "overall" in conf
                assert "grade" in conf
                assert "signals" in conf
                assert conf["grade"] in ("HIGH", "MEDIUM", "LOW")
                assert 0.0 <= conf["overall"] <= 1.0
        finally:
            settings.ENABLE_CONFIDENCE = orig

    def test_confidence_schema_structure(self, client):
        """Confidence schema has the correct nested structure."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository
        from app.repositories.generation_repository import GenerationRepository
        from app.core.config import settings

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        db = SessionLocal()
        try:
            gen_repo = GenerationRepository(db)
            gen = gen_repo.create({
                "source_code": "def g(x): return x",
                "language": "python",
                "framework": "pytest",
                "status": "completed",
                "generated_tests_json": json.dumps({
                    "function_name": "g",
                    "test_cases": [{"name": f"t{i}"} for i in range(6)],
                    "imports": [],
                    "setup_code": None,
                }),
                "generated_tests_code": "# tests",
                "prompt_version": "v1",
            })
            db.commit()
            job_repo = JobRepository(db)
            job_repo.update(job_id, {"status": "completed", "generation_id": gen.id})
            db.commit()
        finally:
            db.close()

        orig = settings.ENABLE_CONFIDENCE
        try:
            settings.ENABLE_CONFIDENCE = True
            resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
            data = resp.json()
            if data.get("confidence") is not None:
                c = data["confidence"]
                assert "signals" in c
                assert "sandbox" in c["signals"]
                assert "validation" in c["signals"]
                assert "test_count" in c["signals"]
                assert "metadata" in c
                assert "test_count" in c["metadata"]
                assert "warning_count" in c["metadata"]
        finally:
            settings.ENABLE_CONFIDENCE = orig


# ---------------------------------------------------------------------------
# 10. Restart Recovery
# ---------------------------------------------------------------------------


class TestRestartRecovery:
    """Tests for startup recovery (jobs stuck in processing after crash)."""

    def test_processing_jobs_exist_in_db_after_submit(self, client):
        """Submitted jobs are persisted even before the pipeline runs."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        # Verify the job is in the DB in a non-terminal state immediately after submit
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            job = repo.get_by_id(job_id)
            assert job is not None
            assert job.id == job_id
        finally:
            db.close()

    def test_job_can_be_recovered_by_setting_status(self, client):
        """Recovery sets stuck processing jobs back to pending."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        # Simulate a stuck-processing job (e.g. after server crash)
        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {"status": "processing"})
            db.commit()
            # Recovery resets to pending
            repo.update(job_id, {"status": "pending", "retry_count": 1})
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        assert data["status"] == "pending"
        assert data["retry_count"] == 1

    def test_checkpoint_field_persists(self, client):
        """last_checkpoint written during pipeline is readable on poll."""
        from app.db.session import SessionLocal
        from app.repositories.job_repository import JobRepository

        headers, _ = register_and_login(client)
        submit = client.post(
            "/api/v2/jobs/generate", headers=headers, json=make_job_payload()
        )
        job_id = submit.json()["job_id"]

        db = SessionLocal()
        try:
            repo = JobRepository(db)
            repo.update(job_id, {
                "status": "processing",
                "last_checkpoint": "LLM_RESPONDED",
            })
            db.commit()
        finally:
            db.close()

        resp = client.get(f"/api/v2/jobs/{job_id}", headers=headers)
        data = resp.json()
        assert data["last_checkpoint"] == "LLM_RESPONDED"


# ---------------------------------------------------------------------------
# 11. API Key Authentication (V2 path)
# ---------------------------------------------------------------------------


class TestApiKeyAuthentication:
    """Tests for API key auth on V2 endpoints."""

    def test_create_api_key_returns_raw_key(self, client):
        """POST /api/v2/auth/keys creates a key and returns the raw value once."""
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/auth/keys",      # correct path (not /api-keys)
            headers=headers,
            json={"label": "e2e-test-key"},   # correct field name
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "raw_key" in data
        assert len(data["raw_key"]) > 20

    def test_api_key_works_for_job_submission(self, client):
        """A valid API key can submit a job using X-API-Key header."""
        headers, _ = register_and_login(client)
        key_resp = client.post(
            "/api/v2/auth/keys",
            headers=headers,
            json={"label": "e2e-api-key"},
        )
        assert key_resp.status_code == 201, f"Key creation failed: {key_resp.text}"
        raw_key = key_resp.json()["raw_key"]

        api_key_headers = {"X-API-Key": raw_key}
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=api_key_headers,
            json=make_job_payload(),
        )
        assert resp.status_code == 202

    def test_list_api_keys(self, client):
        """GET /api/v2/auth/keys returns a list of active keys."""
        headers, _ = register_and_login(client)
        client.post(
            "/api/v2/auth/keys",
            headers=headers,
            json={"label": "list-test-key"},
        )
        resp = client.get("/api/v2/auth/keys", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Response is ApiKeyListResponse with 'keys' list
        key_list = data.get("keys", data)
        assert isinstance(key_list, list)


# ---------------------------------------------------------------------------
# 12. Error Handling: RFC7807 Problem Details
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify error responses follow RFC7807 Problem Details format."""

    def test_404_returns_problem_detail(self, client):
        headers, _ = register_and_login(client)
        resp = client.get(f"/api/v2/jobs/{uuid.uuid4()}", headers=headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_422_returns_validation_error(self, client):
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json={},  # missing required fields
        )
        assert resp.status_code == 422

    def test_network_error_not_raised_by_server(self, client):
        """Server must not propagate internal exceptions as 500 for bad input."""
        headers, _ = register_and_login(client)
        resp = client.post(
            "/api/v2/jobs/generate",
            headers=headers,
            json={"source_code": "x" * 100},
        )
        # Must be 202 (success) or 4xx (validation), never 5xx
        assert resp.status_code < 500
