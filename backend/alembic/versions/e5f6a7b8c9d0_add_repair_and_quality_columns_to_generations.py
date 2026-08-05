"""Add repair and quality columns to generations table.

Revision ID: e5f6a7b8c9d0
Revises:     d4e5f6a7b8c9
Create Date: 2026-08-04

Adds 15 nullable columns that were added to the Generation SQLAlchemy model
(Feature #2: Self-Healing and Feature #3: Quality/Mutation) but never had a
corresponding Alembic migration created.

Missing columns (confirmed by PRAGMA table_info(generations)):
  Self-Healing (Feature #2):
    - repair_attempted        BOOLEAN
    - repair_success          BOOLEAN
    - repair_count            INTEGER
    - repair_duration_ms      FLOAT
    - repair_failure_type     VARCHAR(50)
    - repair_reason           TEXT

  Quality & Mutation Evaluation (Feature #3):
    - quality_score           FLOAT
    - quality_rating          VARCHAR(50)
    - mutation_score          FLOAT
    - killed_mutants          INTEGER
    - survived_mutants        INTEGER
    - timeout_mutants         INTEGER
    - error_mutants           INTEGER
    - smell_count             INTEGER
    - smell_breakdown_json    TEXT

All columns are nullable. This migration is safe to run against a live
database — existing rows will have NULL in these columns, which is the
correct default (same as the Python-level `default=None`/`default=False`/
`default=0` — those only apply at the ORM insert layer, not to existing rows).

The migration is idempotent via try/except per-column so it can be re-run
safely even if a partial upgrade was attempted previously.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.exc import OperationalError

# ---------------------------------------------------------------------------
# Alembic metadata
# ---------------------------------------------------------------------------
revision: str = "e5f6a7b8c9d0"
down_revision: str = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def _safe_add_column(table: str, column: sa.Column) -> None:
    """Add a column only if it does not already exist.

    SQLite does not support IF NOT EXISTS on ALTER TABLE ADD COLUMN,
    so we catch the OperationalError raised when the column already exists
    (e.g. if a previous partial run added some but not all columns).
    """
    try:
        op.add_column(table, column)
    except OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            pass  # column already present — safe to skip
        else:
            raise


def upgrade() -> None:
    """Add self-healing and quality/mutation columns to the generations table."""

    # ── Feature #2: Self-Healing metadata ───────────────────────────────────
    _safe_add_column("generations", sa.Column("repair_attempted",     sa.Boolean(),    nullable=True))
    _safe_add_column("generations", sa.Column("repair_success",       sa.Boolean(),    nullable=True))
    _safe_add_column("generations", sa.Column("repair_count",         sa.Integer(),    nullable=True))
    _safe_add_column("generations", sa.Column("repair_duration_ms",   sa.Float(),      nullable=True))
    _safe_add_column("generations", sa.Column("repair_failure_type",  sa.String(50),   nullable=True))
    _safe_add_column("generations", sa.Column("repair_reason",        sa.Text(),       nullable=True))

    # ── Feature #3: Quality & Mutation Evaluation metadata ──────────────────
    _safe_add_column("generations", sa.Column("quality_score",        sa.Float(),      nullable=True))
    _safe_add_column("generations", sa.Column("quality_rating",       sa.String(50),   nullable=True))
    _safe_add_column("generations", sa.Column("mutation_score",       sa.Float(),      nullable=True))
    _safe_add_column("generations", sa.Column("mutation_duration_ms", sa.Float(),      nullable=True))
    _safe_add_column("generations", sa.Column("killed_mutants",       sa.Integer(),    nullable=True))
    _safe_add_column("generations", sa.Column("survived_mutants",     sa.Integer(),    nullable=True))
    _safe_add_column("generations", sa.Column("timeout_mutants",      sa.Integer(),    nullable=True))
    _safe_add_column("generations", sa.Column("error_mutants",        sa.Integer(),    nullable=True))
    _safe_add_column("generations", sa.Column("smell_count",          sa.Integer(),    nullable=True))
    _safe_add_column("generations", sa.Column("smell_breakdown_json", sa.Text(),       nullable=True))

    # ── Legacy Data Backfill ──────────────────────────────────────────────────
    op.execute("UPDATE generations SET repair_attempted = 0 WHERE repair_attempted IS NULL")
    op.execute("UPDATE generations SET repair_success = 0 WHERE repair_success IS NULL")
    op.execute("UPDATE generations SET repair_count = 0 WHERE repair_count IS NULL")
    op.execute("UPDATE generations SET repair_duration_ms = 0.0 WHERE repair_duration_ms IS NULL")
    op.execute("UPDATE generations SET mutation_duration_ms = 0.0 WHERE mutation_duration_ms IS NULL")



def downgrade() -> None:
    """Remove self-healing and quality/mutation columns from the generations table.

    Note: SQLite does not support DROP COLUMN before version 3.35.0.
    The downgrade is provided for completeness but will raise on older SQLite.
    If downgrade is needed on old SQLite, recreate the table without these columns.
    """
    op.drop_column("generations", "smell_breakdown_json")
    op.drop_column("generations", "smell_count")
    op.drop_column("generations", "error_mutants")
    op.drop_column("generations", "timeout_mutants")
    op.drop_column("generations", "survived_mutants")
    op.drop_column("generations", "killed_mutants")
    op.drop_column("generations", "mutation_score")
    op.drop_column("generations", "quality_rating")
    op.drop_column("generations", "quality_score")
    op.drop_column("generations", "repair_reason")
    op.drop_column("generations", "repair_failure_type")
    op.drop_column("generations", "repair_duration_ms")
    op.drop_column("generations", "repair_count")
    op.drop_column("generations", "repair_success")
    op.drop_column("generations", "repair_attempted")
