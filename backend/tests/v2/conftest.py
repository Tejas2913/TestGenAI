"""Shared test fixtures for all tests/v2/ tests.

Creates an in-memory SQLite database with all tables and a FastAPI TestClient
wired against it. All code paths — including those that call `SessionLocal()`
directly inside service or test helper code — are redirected to the shared
in-memory test engine via monkeypatching.

This conftest is scoped to tests/v2/ only and does not affect the root
conftest or any existing V1 tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401 — register all models so all tables are created
from main import create_app


# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine (one per test session)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all ORM tables once per session, then drop them on teardown."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def force_mock_mode():
    """Force MOCK_MODE=True for the entire test session.

    This guarantees no test ever makes a real LLM API call regardless of
    what MOCK_MODE is set to in .env. All 578 tests remain fast and offline.
    """
    from app.core.config import settings
    original = settings.MOCK_MODE
    # pydantic-settings models are immutable by default; use object.__setattr__
    object.__setattr__(settings, "MOCK_MODE", True)
    yield
    object.__setattr__(settings, "MOCK_MODE", original)



@pytest.fixture()
def db_session(create_test_tables):
    """Yield a per-test DB session wrapped in a savepoint for rollback isolation."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    """Provide a TestClient with all DB access redirected to the test DB.

    Three layers of redirection ensure 100% test isolation:
    1. ``get_db`` — FastAPI dependency used by most endpoints.
    2. ``get_generation_service`` — V1 generation service dependency that
       opens its own ``SessionLocal()`` call.
    3. ``app.db.session.SessionLocal`` — monkeypatched so any code or test
       helper that calls ``SessionLocal()`` directly also hits the test DB.
    """
    import app.db.session as db_session_module
    import dependencies as deps_module
    from dependencies import get_db, get_generation_service, get_job_repository

    # ── Patch 1: disable DB connectivity check on startup ──────────────────
    monkeypatch.setattr(db_session_module, "check_database_connection", lambda: True)

    # ── Patch 2: redirect SessionLocal factory to test engine ───────────────
    # This ensures that any code doing ``from app.db.session import SessionLocal``
    # followed by ``db = SessionLocal()`` will obtain a session connected to the
    # same in-memory test DB (via StaticPool — all sessions share one connection).
    monkeypatch.setattr(db_session_module, "SessionLocal", TestSessionLocal)

    application = create_app()

    # ── Patch 3: FastAPI dependency overrides ───────────────────────────────
    def _override_get_db():
        yield db_session

    def _override_get_generation_service():
        """Return a GenerationService wired to the test session."""
        from app.repositories.generation_repository import GenerationRepository
        from app.services.generation_service import GenerationService

        repo = GenerationRepository(db_session)
        # Provider is not needed for read-path and metadata-only tests.
        # Tests that exercise generation use mocks at the service level.
        try:
            from app.ai.providers.gemini_provider import GeminiProvider
            from app.core.config import settings
            provider = GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model_name=settings.GEMINI_MODEL,
                temperature=settings.GEMINI_TEMPERATURE,
                max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
                timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
                max_retries=settings.GEMINI_MAX_RETRIES,
            )
        except Exception:
            provider = None

        yield GenerationService(repository=repo, llm_provider=provider)

    def _override_get_job_repository():
        from app.repositories.job_repository import JobRepository
        yield JobRepository(db_session)

    application.dependency_overrides[get_db] = _override_get_db
    application.dependency_overrides[get_generation_service] = _override_get_generation_service
    application.dependency_overrides[get_job_repository] = _override_get_job_repository

    with TestClient(application, raise_server_exceptions=True) as c:
        yield c
