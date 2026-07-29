"""Shared test fixtures for Phase 1 tests.

Creates an in-memory SQLite database with all V2.1 tables and
a FastAPI TestClient wired against it.

This conftest is scoped to tests/v2/ only and does not affect
the root conftest or any existing V1 tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401 — register all models including V2.1 ones
from main import create_app


# ---------------------------------------------------------------------------
# In-memory test database (isolated per test session)
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
    """Create all tables in the in-memory test database once per session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session(create_test_tables):
    """Yield a fresh DB session per test, rolled back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session, monkeypatch):
    """Provide a TestClient with the test DB session wired into get_db."""
    import app.db.session as db_session_module
    from dependencies import get_db

    monkeypatch.setattr(db_session_module, "check_database_connection", lambda: True)

    application = create_app()

    def _override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = _override_get_db

    with TestClient(application, raise_server_exceptions=True) as c:
        yield c
