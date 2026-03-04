"""Add graph lock columns to automations for collaborative editing.

Revision ID: 003
Revises: 002
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column(
            "locked_by",
            sa.UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "automations",
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("automations", "locked_at")
    op.drop_column("automations", "locked_by")
