"""Add trigger_tags, is_trigger_enabled to automations, and automation_trigger_log table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add trigger columns to automations
    op.add_column(
        "automations",
        sa.Column("trigger_tags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=True),
    )
    op.add_column(
        "automations",
        sa.Column("is_trigger_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # GIN index for trigger_tags overlap queries
    op.create_index("idx_automations_trigger_tags", "automations", ["trigger_tags"], postgresql_using="gin")

    # Create automation_trigger_log table
    op.create_table(
        "automation_trigger_log",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("automation_id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=True),
        sa.Column("matched_tags", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'triggered'")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["execution_logs.id"]),
    )
    op.create_index("idx_trigger_log_automation", "automation_trigger_log", ["automation_id"])
    op.create_index("idx_trigger_log_incident", "automation_trigger_log", ["incident_id"])


def downgrade() -> None:
    op.drop_table("automation_trigger_log")
    op.drop_index("idx_automations_trigger_tags", table_name="automations")
    op.drop_column("automations", "is_trigger_enabled")
    op.drop_column("automations", "trigger_tags")
