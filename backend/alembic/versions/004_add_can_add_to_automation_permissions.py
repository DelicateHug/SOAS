"""Add can_add column to automation_permissions table.

Revision ID: 004
Revises: 003
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_permissions",
        sa.Column("can_add", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("automation_permissions", "can_add")
