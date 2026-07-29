"""Unit tests for Phase 4 database persistence of Self-Healing metadata.

Verifies:
  - Generation ORM model includes repair_attempted, repair_success, repair_count, repair_duration_ms, repair_failure_type, and repair_reason columns.
  - Successful repairs persist repair_attempted=True, repair_success=True, repair_count=1, repair_duration_ms, repair_failure_type, repair_reason.
  - Failed repairs persist repair_attempted=True, repair_success=False, repair_count=1, repair_duration_ms, repair_failure_type, repair_reason.
  - Non-repairable failures persist repair_attempted=False, repair_success=False, repair_count=0, repair_failure_type, repair_reason.
"""

from unittest.mock import MagicMock
import pytest

from app.models.generation import Generation
from app.sandbox.schemas import SandboxExecuteResponse
from app.services.job_engine import _run_job_sync


class TestSelfHealPersistence:
    """Phase 4 database persistence tests."""

    def test_generation_model_has_self_healing_columns(self, db_session) -> None:
        gen = Generation(
            source_code="def add(a, b): return a + b",
            language="python",
            framework="pytest",
        )
        db_session.add(gen)
        db_session.commit()
        db_session.refresh(gen)

        assert hasattr(gen, "repair_attempted")
        assert hasattr(gen, "repair_success")
        assert hasattr(gen, "repair_count")
        assert hasattr(gen, "repair_duration_ms")
        assert hasattr(gen, "repair_failure_type")
        assert hasattr(gen, "repair_reason")

        assert gen.repair_attempted is False
        assert gen.repair_success is False
        assert gen.repair_count == 0

    def test_job_engine_persists_repair_success_metadata(self, db_session, monkeypatch) -> None:
        from app.models.job import GenerationJob
        from app.repositories.job_repository import JobRepository
        from app.repositories.generation_repository import GenerationRepository

        # Create user & job records
        gen = Generation(
            source_code="def calc(a, b): return a + b",
            generated_tests_code="def test_calc(): calc()",
            language="python",
            framework="pytest",
            status="completed",
        )
        db_session.add(gen)
        db_session.commit()
        db_session.refresh(gen)

        job = GenerationJob(
            status="pending",
            generation_id=gen.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        input_data = {"source_code": gen.source_code}

        # Mock SandboxClient: 1st (gen service) & 2nd (_self_heal init) fail with TypeError, 3rd (_self_heal 2nd run) passes
        mock_sandbox = MagicMock()
        mock_sandbox.execute.side_effect = [
            SandboxExecuteResponse(exit_code=1, stdout="", stderr="TypeError: calc() missing 2 required positional arguments", duration_ms=100.0),
            SandboxExecuteResponse(exit_code=1, stdout="", stderr="TypeError: calc() missing 2 required positional arguments", duration_ms=100.0),
            SandboxExecuteResponse(exit_code=0, stdout="1 passed", stderr="", duration_ms=110.0),
            SandboxExecuteResponse(exit_code=0, stdout="1 passed", stderr="", duration_ms=110.0),
        ]
        monkeypatch.setattr("app.sandbox.client.SandboxClient.execute", mock_sandbox.execute)

        # Mock LLM provider: 1st call returns initial JSON, 2nd call returns repaired code
        import json
        initial_json = json.dumps({
            "test_cases": [
                {
                    "name": "test_calc",
                    "description": "Test calc function",
                    "category": "unit",
                    "expected_output": "3",
                    "code": "def test_calc(): calc()",
                }
            ]
        })
        mock_provider = MagicMock()
        mock_provider.last_usage = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        mock_provider.generate.side_effect = [
            initial_json,
            "def test_calc(): assert calc(1, 2) == 3",
        ]
        monkeypatch.setattr("app.services.job_engine.GeminiProvider", lambda *a, **kw: mock_provider)

        # Enable sandbox & self heal in settings
        from app.core.config import settings
        from tests.v2.conftest import TestSessionLocal
        monkeypatch.setattr(settings, "ENABLE_SANDBOX", True)
        monkeypatch.setattr(settings, "ENABLE_SELF_HEAL", True)
        monkeypatch.setattr("app.services.job_engine.SessionLocal", TestSessionLocal)

        job_id = job.id
        _run_job_sync(job_id, input_data)

        # Verify persisted fields on generation in a fresh test session
        verify_db = TestSessionLocal()
        try:
            job_updated = verify_db.get(GenerationJob, job_id)
            assert job_updated is not None
            assert job_updated.generation_id is not None
            gen_updated = verify_db.get(Generation, job_updated.generation_id)
            assert gen_updated is not None
            assert gen_updated.repair_attempted is True
            assert gen_updated.repair_success is True
            assert gen_updated.repair_count == 1
            assert gen_updated.repair_duration_ms > 0.0
            assert gen_updated.repair_failure_type == "TYPE_ERROR"
            assert gen_updated.repair_reason == "Missing required positional argument"
        finally:
            verify_db.close()
