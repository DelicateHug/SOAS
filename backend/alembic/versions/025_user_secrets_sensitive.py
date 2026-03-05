"""Add sensitive flag to user_secrets table.

Revision ID: 025
Revises: 024
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_secrets",
        sa.Column("sensitive", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_secrets", "sensitive")
