"""Integration tests for the generation pipeline.

Uses a mock LLM provider to test the full service layer
without making real API calls. Tests cover:
- Successful generation
- Invalid Python code
- Malformed LLM response
- Empty LLM response
- Timeout simulation
- Retry simulation
- Validation failure (empty test_cases)
- Large source file rejection
- Large specification rejection
- Empty specification (allowed)
"""

import json
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.providers.base import LLMProvider
from app.core.config import settings
from app.db.base import Base
from app.domain.prompt_payload import PromptPayload
from app.exceptions import (
    InputTooLargeException,
    LLMException,
    LLMRetryExhaustedException,
    LLMTimeoutException,
    ValidationException,
)
from app.models.generation import Generation
from app.repositories.generation_repository import GenerationRepository
from app.services.generation_service import GenerationService


# ---------------------------------------------------------------------------
# Mock LLM Providers
# ---------------------------------------------------------------------------

VALID_LLM_RESPONSE = json.dumps({
    "function_name": "add",
    "test_cases": [
        {
            "name": "test_add_positive",
            "description": "Add two positive integers",
            "category": "happy_path",
            "inputs": {"a": 2, "b": 3},
            "expected_output": 5,
            "assertions": ["assert add(2, 3) == 5"],
        },
        {
            "name": "test_add_zero",
            "description": "Add zero to a number",
            "category": "edge_case",
            "inputs": {"a": 0, "b": 5},
            "expected_output": 5,
            "assertions": ["assert add(0, 5) == 5"],
        },
        {
            "name": "test_add_negative",
            "description": "Add negative numbers",
            "category": "error_handling",
            "inputs": {"a": -1, "b": -2},
            "expected_output": -3,
            "assertions": ["assert add(-1, -2) == -3"],
        },
    ],
    "imports": ["from mymodule import add"],
    "setup_code": None,
})


class MockSuccessProvider(LLMProvider):
    """Returns a valid JSON response."""

    def __init__(self):
        self.last_usage = {
            "input_tokens": 150,
            "output_tokens": 300,
            "total_tokens": 450,
            "duration_ms": 1200.0,
            "retry_count": 0,
            "model": "mock-model",
        }

    def generate(self, payload: PromptPayload) -> str:
        return VALID_LLM_RESPONSE


class MockMalformedProvider(LLMProvider):
    """Returns invalid JSON."""

    def generate(self, payload: PromptPayload) -> str:
        return "This is not JSON at all, just plain text without braces"


class MockEmptyResponseProvider(LLMProvider):
    """Returns valid JSON with empty test_cases."""

    def generate(self, payload: PromptPayload) -> str:
        return json.dumps({
            "function_name": "add",
            "test_cases": [],
            "imports": [],
            "setup_code": None,
        })


class MockTimeoutProvider(LLMProvider):
    """Simulates a timeout exception."""

    def generate(self, payload: PromptPayload) -> str:
        raise LLMTimeoutException(detail="Request timed out after 60s")


class MockRetryExhaustedProvider(LLMProvider):
    """Simulates exhausted retries."""

    def __init__(self):
        self.last_usage = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "duration_ms": 15000.0,
            "retry_count": 3,
            "model": "mock-model",
        }

    def generate(self, payload: PromptPayload) -> str:
        raise LLMRetryExhaustedException(
            detail="Failed after 3 attempts: 429 Resource exhausted",
            attempts=3,
        )


class MockLLMErrorProvider(LLMProvider):
    """Simulates a generic LLM error."""

    def generate(self, payload: PromptPayload) -> str:
        raise LLMException(detail="Internal server error from Gemini")


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

VALID_SOURCE = "def add(a, b):\n    return a + b\n"


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_service(session, provider):
    """Create a GenerationService with the given mock provider."""
    repo = GenerationRepository(session)
    return GenerationService(repository=repo, llm_provider=provider)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestSuccessfulGeneration:
    """Tests for successful end-to-end generation."""

    def test_successful_generation(self, db_session):
        """Full pipeline produces completed record with test code."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record is not None
        assert record.status == "completed"
        assert record.generated_tests_code is not None
        assert "test_add_positive" in record.generated_tests_code
        assert "test_add_zero" in record.generated_tests_code
        assert record.generated_tests_json is not None
        assert record.error_message is None

    def test_prompt_version_stored(self, db_session):
        """Prompt version is persisted on the record."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.prompt_version == settings.PROMPT_VERSION

    def test_token_usage_stored(self, db_session):
        """Token usage from provider is persisted."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.input_tokens == 150
        assert record.output_tokens == 300
        assert record.total_tokens == 450

    def test_duration_stored(self, db_session):
        """Pipeline duration is recorded."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.duration_ms is not None
        assert record.duration_ms >= 0

    def test_empty_specification_allowed(self, db_session):
        """Generation succeeds with no specification."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(
            source_code=VALID_SOURCE, specification=None
        )

        assert record.status == "completed"


class TestInvalidInput:
    """Tests for invalid input handling."""

    def test_invalid_python_code(self, db_session):
        """Invalid Python syntax is caught by InputAnalyser."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(source_code="def <<<invalid>>>:")

        assert record.status == "failed"
        assert record.error_message is not None

    def test_large_source_code_rejected(self, db_session):
        """Source code exceeding MAX_SOURCE_CODE_SIZE is rejected."""
        service = _make_service(db_session, MockSuccessProvider())
        oversized = "x = 1\n" * (settings.MAX_SOURCE_CODE_SIZE + 1)

        # InputTooLargeException is raised before DB record is created,
        # so the service should raise it directly.
        with pytest.raises(InputTooLargeException, match="Source code exceeds"):
            service.generate(source_code=oversized)

    def test_large_specification_rejected(self, db_session):
        """Specification exceeding MAX_SPECIFICATION_SIZE is rejected."""
        service = _make_service(db_session, MockSuccessProvider())
        oversized_spec = "a" * (settings.MAX_SPECIFICATION_SIZE + 1)

        with pytest.raises(InputTooLargeException, match="Specification exceeds"):
            service.generate(
                source_code=VALID_SOURCE, specification=oversized_spec
            )


class TestLLMFailures:
    """Tests for LLM provider failure handling."""

    def test_malformed_llm_response(self, db_session):
        """Unparseable LLM response results in a failed record."""
        service = _make_service(db_session, MockMalformedProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.status == "failed"
        assert "JSON" in record.error_message

    def test_empty_test_cases_response(self, db_session):
        """LLM returns valid JSON but with empty test_cases."""
        service = _make_service(db_session, MockEmptyResponseProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.status == "failed"
        assert "no test cases" in record.error_message.lower()

    def test_timeout(self, db_session):
        """LLM timeout produces a failed record with timeout message."""
        service = _make_service(db_session, MockTimeoutProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.status == "failed"
        assert "timed out" in record.error_message.lower()

    def test_retry_exhausted(self, db_session):
        """Exhausted retries produce a failed record."""
        service = _make_service(db_session, MockRetryExhaustedProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.status == "failed"
        assert "retry" in record.error_message.lower() or "attempts" in record.error_message.lower()

    def test_generic_llm_error(self, db_session):
        """Generic LLM error produces a failed record."""
        service = _make_service(db_session, MockLLMErrorProvider())
        record = service.generate(source_code=VALID_SOURCE)

        assert record.status == "failed"
        assert record.error_message is not None


class TestHistoryAndRetrieval:
    """Tests for get_by_id and get_history."""

    def test_get_by_id(self, db_session):
        """Can retrieve a generation by its ID."""
        service = _make_service(db_session, MockSuccessProvider())
        record = service.generate(source_code=VALID_SOURCE)

        found = service.get_by_id(record.id)
        assert found is not None
        assert found.id == record.id

    def test_get_by_id_not_found(self, db_session):
        """Returns None for a non-existent ID."""
        service = _make_service(db_session, MockSuccessProvider())
        assert service.get_by_id("nonexistent") is None

    def test_history_pagination(self, db_session):
        """History returns paginated results."""
        service = _make_service(db_session, MockSuccessProvider())

        # Create 3 records
        for _ in range(3):
            service.generate(source_code=VALID_SOURCE)

        items, total = service.get_history(page=1, size=2)
        assert total == 3
        assert len(items) == 2

        items2, total2 = service.get_history(page=2, size=2)
        assert total2 == 3
        assert len(items2) == 1
