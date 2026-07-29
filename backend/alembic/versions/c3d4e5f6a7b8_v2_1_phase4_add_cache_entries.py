"""Phase 4 — Add cache_entries table for L2 persistent cache.

Revision ID: c3d4e5f6a7b8
Revises:     b2c3d4e5f6a7
Create Date: 2026-07-23

Adds:
  cache_entries table (L2 persistent cache for deterministic generation results).

This migration is additive. No existing tables are modified.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Alembic metadata
# ---------------------------------------------------------------------------
revision: str = "c3d4e5f6a7b8"
down_revision: str = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the cache_entries table."""
    op.create_table(
        "cache_entries",
        # ----------------------------------------------------------------
        # Primary key (UUID, from BaseModel)
        # ----------------------------------------------------------------
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        # ----------------------------------------------------------------
        # Request identity
        # ----------------------------------------------------------------
        sa.Column(
            "cache_key",
            sa.String(64),
            nullable=False,
            unique=True,
            comment="SHA-256 hex of (source_code|specification|language|framework|prompt_version)",
        ),
        sa.Column(
            "prompt_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 of the active prompt template version string",
        ),

        # ----------------------------------------------------------------
        # Generated artifacts
        # ----------------------------------------------------------------
        sa.Column("generated_tests_json", sa.Text, nullable=True),
        sa.Column("generated_tests_code", sa.Text, nullable=True),

        # ----------------------------------------------------------------
        # Request metadata
        # ----------------------------------------------------------------
        sa.Column("language", sa.String(50), nullable=False, server_default="python"),
        sa.Column("framework", sa.String(50), nullable=False, server_default="pytest"),

        # ----------------------------------------------------------------
        # Cache management
        # ----------------------------------------------------------------
        sa.Column(
            "hit_count",
            sa.Integer,
            nullable=False,
            server_default="0",
            comment="Incremented each time this entry is served from L2 cache",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime,
            nullable=True,
            comment="UTC expiry. NULL = entry never expires.",
        ),

        # ----------------------------------------------------------------
        # Timestamps (from BaseModel)
        # ----------------------------------------------------------------
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # ----------------------------------------------------------------
    # Indexes
    # ----------------------------------------------------------------
    op.create_index(
        "ix_cache_entries_cache_key",
        "cache_entries",
        ["cache_key"],
        unique=True,
    )
    op.create_index(
        "ix_cache_entries_prompt_hash",
        "cache_entries",
        ["prompt_hash"],
        unique=False,
    )
    op.create_index(
        "ix_cache_entries_expires_at",
        "cache_entries",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the cache_entries table and its indexes."""
    op.drop_index("ix_cache_entries_expires_at", table_name="cache_entries")
    op.drop_index("ix_cache_entries_prompt_hash", table_name="cache_entries")
    op.drop_index("ix_cache_entries_cache_key", table_name="cache_entries")
    op.drop_table("cache_entries")
