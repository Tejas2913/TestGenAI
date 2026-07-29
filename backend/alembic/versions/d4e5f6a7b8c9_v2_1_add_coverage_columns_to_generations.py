"""Add coverage columns to generations table.

Revision ID: d4e5f6a7b8c9
Revises:     c3d4e5f6a7b8
Create Date: 2026-07-28

Adds 5 nullable columns to generations table for coverage.py integration:
  - coverage_line_pct
  - coverage_branch_pct
  - coverage_total_statements
  - coverage_covered_statements
  - coverage_missing_statements
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Alembic metadata
# ---------------------------------------------------------------------------
revision: str = "d4e5f6a7b8c9"
down_revision: str = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable coverage columns to the generations table."""
    op.add_column("generations", sa.Column("coverage_line_pct", sa.Float(), nullable=True))
    op.add_column("generations", sa.Column("coverage_branch_pct", sa.Float(), nullable=True))
    op.add_column("generations", sa.Column("coverage_total_statements", sa.Integer(), nullable=True))
    op.add_column("generations", sa.Column("coverage_covered_statements", sa.Integer(), nullable=True))
    op.add_column("generations", sa.Column("coverage_missing_statements", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove coverage columns from the generations table."""
    op.drop_column("generations", "coverage_missing_statements")
    op.drop_column("generations", "coverage_covered_statements")
    op.drop_column("generations", "coverage_total_statements")
    op.drop_column("generations", "coverage_branch_pct")
    op.drop_column("generations", "coverage_line_pct")
