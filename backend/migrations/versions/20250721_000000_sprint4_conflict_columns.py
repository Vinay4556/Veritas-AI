"""Sprint 4: Add columns to conflict_declarations and rename declared_by to officer_id.

Revision ID: c9e4d3b2a156
Revises: b7d3c2a1f804
Create Date: 2025-07-21 00:00:00.000000
"""

# revision identifiers, used by Alembic.
revision = 'c9e4d3b2a156'
down_revision = 'b7d3c2a1f804'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Rename declared_by to officer_id
    op.execute(
        "ALTER TABLE conflict_declarations RENAME COLUMN declared_by TO officer_id"
    )
    # Add officer_name column
    op.execute(
        "ALTER TABLE conflict_declarations "
        "ADD COLUMN IF NOT EXISTS officer_name VARCHAR(200)"
    )
    # Add has_conflict column
    op.execute(
        "ALTER TABLE conflict_declarations "
        "ADD COLUMN IF NOT EXISTS has_conflict BOOLEAN NOT NULL DEFAULT FALSE"
    )
    # Add action column
    op.execute(
        "ALTER TABLE conflict_declarations "
        "ADD COLUMN IF NOT EXISTS action VARCHAR(20) DEFAULT 'NONE'"
    )


def downgrade() -> None:
    # Drop added columns in reverse order
    op.execute(
        "ALTER TABLE conflict_declarations DROP COLUMN IF EXISTS action"
    )
    op.execute(
        "ALTER TABLE conflict_declarations DROP COLUMN IF EXISTS has_conflict"
    )
    op.execute(
        "ALTER TABLE conflict_declarations DROP COLUMN IF EXISTS officer_name"
    )
    # Rename officer_id back to declared_by
    op.execute(
        "ALTER TABLE conflict_declarations RENAME COLUMN officer_id TO declared_by"
    )
