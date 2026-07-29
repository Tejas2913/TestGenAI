"""SQLAlchemy engine and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed after use."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    """Perform a lightweight database connectivity check."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def dispose_engine() -> None:
    """Dispose the engine, closing all pooled connections."""
    engine.dispose()
