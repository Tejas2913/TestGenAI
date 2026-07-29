"""ApiKey ORM model — V2.1.

Personal API keys for headless / programmatic access to TestGen AI.
Keys are hashed before storage — the raw key is never persisted.

Phase 2 will implement key generation, hashing (SHA-256), and validation.
Phase 1 creates the schema to allow the Phase 2 migration to be purely additive.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class ApiKey(BaseModel):
    """A hashed personal API key linked to a user.

    Responsibilities:
        - Headless API authentication (Phase 2 enforcement)
        - Revocation via revoked_at timestamp
        - Human-readable label for user key management

    The raw key value is NEVER stored. Only a SHA-256 hash is persisted.
    Phase 2 will add the generation and validation logic.
    """

    __tablename__ = "api_keys"

    # ----------------------------------------------------------------
    # Ownership
    # ----------------------------------------------------------------
    user_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    # ----------------------------------------------------------------
    # Key storage — SHA-256 hash of the raw key (Phase 2 enforces this)
    # ----------------------------------------------------------------
    key_hash: Mapped[str] = mapped_column(
        String(64),   # SHA-256 hex digest is always 64 characters
        nullable=False,
        unique=True,
        index=True,
    )

    # Human-readable label set by the user (e.g. "CI pipeline key")
    label: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ----------------------------------------------------------------
    # Revocation — NULL means the key is active, timestamp means revoked.
    # Phase 2 checks this column during validation.
    # ----------------------------------------------------------------
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
