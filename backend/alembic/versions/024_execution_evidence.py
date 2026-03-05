"""Add is_evidence column to execution_logs table.

Revision ID: 024
Revises: 023
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_logs",
        sa.Column("is_evidence", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index(
        "idx_executions_incident_evidence",
        "execution_logs",
        ["incident_id", "is_evidence"],
    )
    op.create_index(
        "idx_executions_case_evidence",
        "execution_logs",
        ["case_id", "is_evidence"],
    )


def downgrade() -> None:
    op.drop_index("idx_executions_case_evidence", table_name="execution_logs")
    op.drop_index("idx_executions_incident_evidence", table_name="execution_logs")
    op.drop_column("execution_logs", "is_evidence")
