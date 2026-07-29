"""Unit tests for Phase 5 API serialization of Self-Healing metadata.

Verifies:
  - GenerationResponse includes repair_attempted, repair_success, repair_count, repair_duration_ms, repair_failure_type, and repair_reason.
  - Successful generation without repair returns defaults (repair_attempted=False, repair_success=False, repair_count=0, repair_duration_ms=0.0, repair_failure_type=None, repair_reason=None).
  - Generation record with repair metadata serializes all fields accurately.
"""

from datetime import datetime
from app.schemas.generation import GenerationResponse, GenerationStatus


class TestSelfHealAPISerialization:
    """Phase 5 API serialization unit tests."""

    def test_default_generation_response_serialization(self) -> None:
        """Verify default self-healing values on GenerationResponse."""
        resp = GenerationResponse(
            id="gen-123",
            source_code="def add(a, b): return a + b",
            specification=None,
            language="python",
            framework="pytest",
            status=GenerationStatus.COMPLETED,
            generated_tests_json=None,
            generated_tests_code="def test_add(): assert add(1, 2) == 3",
            error_message=None,
            prompt_version="v1",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            duration_ms=150.0,
            architecture_version="2.1",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert resp.repair_attempted is False
        assert resp.repair_success is False
        assert resp.repair_count == 0
        assert resp.repair_duration_ms == 0.0
        assert resp.repair_failure_type is None
        assert resp.repair_reason is None

    def test_repaired_generation_response_serialization(self) -> None:
        """Verify populated self-healing metadata serialization on GenerationResponse."""
        resp = GenerationResponse(
            id="gen-456",
            source_code="def add(a, b): return a + b",
            specification=None,
            language="python",
            framework="pytest",
            status=GenerationStatus.COMPLETED,
            generated_tests_json=None,
            generated_tests_code="def test_add(): assert add(1, 2) == 3",
            error_message=None,
            prompt_version="v1",
            input_tokens=15,
            output_tokens=25,
            total_tokens=40,
            duration_ms=250.0,
            architecture_version="2.1",
            repair_attempted=True,
            repair_success=True,
            repair_count=1,
            repair_duration_ms=248.7,
            repair_failure_type="TYPE_ERROR",
            repair_reason="Missing required positional argument",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        data = resp.model_dump()
        assert data["repair_attempted"] is True
        assert data["repair_success"] is True
        assert data["repair_count"] == 1
        assert data["repair_duration_ms"] == 248.7
        assert data["repair_failure_type"] == "TYPE_ERROR"
        assert data["repair_reason"] == "Missing required positional argument"
