"""Sprint 3: persistent token revocation table.

Revision ID: b7d3c2a1f804
Revises: a3f91b2c8e47
Create Date: 2025-07-20 00:00:00.000000
"""

# revision identifiers, used by Alembic.
revision = 'b7d3c2a1f804'
down_revision = 'a3f91b2c8e47'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_hash   VARCHAR(64)  PRIMARY KEY,
            revoked_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            expires_at   TIMESTAMPTZ  NOT NULL
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at
            ON revoked_tokens(expires_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS revoked_tokens")
