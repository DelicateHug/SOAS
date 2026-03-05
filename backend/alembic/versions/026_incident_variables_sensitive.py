"""Add sensitive flag to incident_variables table.

Revision ID: 026
Revises: 025
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "incident_variables",
        sa.Column("sensitive", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("incident_variables", "sensitive")
