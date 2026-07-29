"""User ORM model — V2.1.

Represents a registered user for authentication and quota enforcement.
Passwords are stored as Argon2 hashes — never in plaintext.
Phase 2 will add the hashing logic and JWT issuance on top of this model.
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class User(BaseModel):
    """A registered TestGen AI user.

    Responsibilities:
        - Identity (email, display name)
        - Credential storage (hashed password — Phase 2 enforces hashing)
        - Soft-disable (is_active flag)
        - org_id placeholder for future multi-tenancy (nullable)

    Phase 1 creates the schema. Phase 2 adds auth business logic.
    """

    __tablename__ = "users"

    # ----------------------------------------------------------------
    # Identity
    # ----------------------------------------------------------------
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )

    display_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # ----------------------------------------------------------------
    # Credential — stored as an Argon2 hash in Phase 2.
    # Nullable now so the Phase 1 migration does not break anything.
    # Phase 2 will enforce non-null via application logic.
    # ----------------------------------------------------------------
    hashed_password: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ----------------------------------------------------------------
    # State
    # ----------------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # ----------------------------------------------------------------
    # Future multi-tenancy anchor — nullable, never enforced in V2.1
    # ----------------------------------------------------------------
    org_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
