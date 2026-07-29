"""v2.1 phase 1 — add users, api_keys, generation_jobs tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-21

V2.1 Phase 1 — Data Model Foundations

This migration is PURELY ADDITIVE:
  - Creates three new tables: users, api_keys, generation_jobs
  - Does NOT alter any existing tables or columns
  - Does NOT drop any existing tables or columns
  - Safe to run against a live database with existing V1 records

Rollback (downgrade):
  Drops the three new tables.
  Existing V1 data in the generations table is unaffected.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the users, api_keys, and generation_jobs tables."""

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_org_id", "users", ["org_id"], unique=False)

    # ------------------------------------------------------------------
    # api_keys
    # ------------------------------------------------------------------
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    # ------------------------------------------------------------------
    # generation_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("generation_id", sa.String(36), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checkpoint", sa.String(50), nullable=True),
        sa.Column("checkpoint_payload", sa.Text(), nullable=True),
        sa.Column("checkpoint_updated_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_generation_jobs_status", "generation_jobs", ["status"], unique=False
    )
    op.create_index(
        "ix_generation_jobs_user_id", "generation_jobs", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Drop the three V2.1 Phase 1 tables.

    The existing generations table is NOT affected.
    """
    op.drop_table("generation_jobs")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
