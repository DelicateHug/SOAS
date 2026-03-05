"""Add collaboration lock columns to automations table.

Revision ID: 029
Revises: 028
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automations",
        sa.Column("locked_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "automations",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automations", "locked_at")
    op.drop_column("automations", "locked_by")
