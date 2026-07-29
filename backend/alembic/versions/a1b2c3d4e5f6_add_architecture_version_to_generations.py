"""add_architecture_version_to_generations

Revision ID: a1b2c3d4e5f6
Revises: 83e2d64be244
Create Date: 2026-07-17

Adds architecture_version column to the generations table.

This is an additive, non-breaking migration:
- Column is nullable — existing rows will have NULL (treated as pre-V1.0 / legacy)
- New records created by V1.0 service will always carry architecture_version = "1.0"
- Safe to run against a live database without downtime (SQLite ALTER TABLE is safe)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '83e2d64be244'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add architecture_version column to generations table."""
    op.add_column(
        'generations',
        sa.Column('architecture_version', sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    """Remove architecture_version column from generations table."""
    op.drop_column('generations', 'architecture_version')
