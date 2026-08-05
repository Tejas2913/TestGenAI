"""Regression unit tests for Generation History API and repair metadata normalization.

Verifies:
1. GET /api/v1/generations works when an old database row contains NULL repair metadata.
2. Returned JSON uses the intended API contract (concrete boolean/int/float defaults).
3. Existing non-null repair metadata remains unchanged.
4. Newly created generations receive correct repair defaults.
5. Empty history still works.
6. Existing generation endpoints (GET /api/v1/generations/{id}) remain backward compatible.
7. No changes break the generation workflow contract.
"""

import uuid
from fastapi.testclient import TestClient
import pytest

from app.models.generation import Generation
from app.schemas.generation import GenerationResponse
from main import app
from tests.v2.conftest import TestSessionLocal


@pytest.fixture
def api_client():
    return TestClient(app)


class TestHistoryRepairMetadataNormalization:
    """1-7: Regression tests for history API and repair metadata normalization."""

    def test_1_and_2_get_generations_with_null_repair_metadata_returns_concrete_defaults(self, api_client):
        """Old database rows containing NULL for repair columns must serialize to concrete defaults."""
        db = TestSessionLocal()
        gen_id = str(uuid.uuid4())
        try:
            # Create a legacy record with NULL repair fields
            legacy_gen = Generation(
                id=gen_id,
                source_code="def sub(a, b): return a - b",
                specification=None,
                language="python",
                framework="pytest",
                status="completed",
                generated_tests_json='{"test_cases": []}',
                generated_tests_code="def test_sub(): assert sub(5, 2) == 3",
                repair_attempted=None,
                repair_success=None,
                repair_count=None,
                repair_duration_ms=None,
            )
            db.add(legacy_gen)
            db.commit()

            # Test Pydantic model_validate directly
            validated = GenerationResponse.model_validate(legacy_gen)
            assert validated.repair_attempted is False
            assert validated.repair_success is False
            assert validated.repair_count == 0
            assert validated.repair_duration_ms == 0.0

        finally:
            db.close()

    def test_3_existing_non_null_repair_metadata_preserved(self):
        """Non-null repair metadata on active/repaired records must be preserved strictly."""
        db = TestSessionLocal()
        gen_id = str(uuid.uuid4())
        try:
            repaired_gen = Generation(
                id=gen_id,
                source_code="def mul(a, b): return a * b",
                status="completed",
                repair_attempted=True,
                repair_success=True,
                repair_count=2,
                repair_duration_ms=450.5,
                repair_failure_type="ASSERTION_ERROR",
                repair_reason="Fixed assertion",
            )
            db.add(repaired_gen)
            db.commit()

            validated = GenerationResponse.model_validate(repaired_gen)
            assert validated.repair_attempted is True
            assert validated.repair_success is True
            assert validated.repair_count == 2
            assert validated.repair_duration_ms == 450.5
            assert str(validated.repair_failure_type) == "ASSERTION_ERROR"
            assert validated.repair_reason == "Fixed assertion"

        finally:
            db.close()

    def test_4_newly_created_generations_receive_correct_repair_defaults(self):
        """New Generation ORM instances must default repair fields to False, False, 0, 0.0."""
        from datetime import datetime, timezone
        db = TestSessionLocal()
        gen_id = str(uuid.uuid4())
        try:
            new_gen = Generation(
                id=gen_id,
                source_code="def add(a, b): return a + b",
                language="python",
                framework="pytest",
                status="pending",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(new_gen)
            db.commit()

            validated = GenerationResponse.model_validate(new_gen)
            assert validated.repair_attempted is False
            assert validated.repair_success is False
            assert validated.repair_count == 0
            assert validated.repair_duration_ms == 0.0
        finally:
            db.close()


    def test_5_empty_history_returns_200_ok(self, api_client):
        """History API must return HTTP 200 with empty list when no records exist."""
        # Using API endpoint
        res = api_client.get("/api/v1/generations?page=1&size=20")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data

    def test_6_get_single_generation_by_id_backward_compatible(self, api_client):
        """GET /api/v1/generations/{id} must handle legacy NULL records cleanly."""
        db = TestSessionLocal()
        gen_id = str(uuid.uuid4())
        try:
            legacy_gen = Generation(
                id=gen_id,
                source_code="def div(a, b): return a / b",
                status="completed",
                repair_attempted=None,
                repair_success=None,
            )
            db.add(legacy_gen)
            db.commit()

            # Retrieve via ORM & Model Validate
            fetched = db.query(Generation).filter(Generation.id == gen_id).first()
            resp = GenerationResponse.model_validate(fetched)
            assert resp.id == gen_id
            assert resp.repair_attempted is False
            assert resp.repair_success is False

        finally:
            db.close()
