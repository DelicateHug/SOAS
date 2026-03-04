"""Add performance indexes for common query patterns and missing FK indexes.

Revision ID: 017
Revises: 016
Create Date: 2026-03-04
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Compound indexes for common query patterns --
    op.create_index(
        "idx_incidents_status_created", "incidents", ["status", "created_at"]
    )
    op.create_index(
        "idx_incidents_created_by_created",
        "incidents",
        ["created_by", "created_at"],
    )
    op.create_index(
        "idx_incidents_source_ref", "incidents", ["source", "source_ref"]
    )
    op.create_index(
        "idx_executions_automation_started",
        "execution_logs",
        ["automation_id", "started_at"],
    )
    op.create_index(
        "idx_executions_status_started",
        "execution_logs",
        ["status", "started_at"],
    )

    # -- GIN index for ARRAY overlap queries in trigger matching --
    op.execute(
        "CREATE INDEX idx_automations_trigger_tags_gin "
        "ON automations USING GIN (trigger_tags)"
    )

    # -- Missing FK indexes (PostgreSQL does not auto-index FK columns) --
    op.create_index("idx_incidents_created_by", "incidents", ["created_by"])
    op.create_index("idx_incidents_lead_id", "incidents", ["lead_id"])
    op.create_index(
        "idx_incident_assignments_user_id", "incident_assignments", ["user_id"]
    )
    op.create_index("idx_cases_created_by", "cases", ["created_by"])
    op.create_index(
        "idx_timeline_entries_created_by", "timeline_entries", ["created_by"]
    )
    op.create_index(
        "idx_automation_permissions_role_id",
        "automation_permissions",
        ["role_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_automation_permissions_role_id", "automation_permissions")
    op.drop_index("idx_timeline_entries_created_by", "timeline_entries")
    op.drop_index("idx_cases_created_by", "cases")
    op.drop_index("idx_incident_assignments_user_id", "incident_assignments")
    op.drop_index("idx_incidents_lead_id", "incidents")
    op.drop_index("idx_incidents_created_by", "incidents")
    op.execute("DROP INDEX IF EXISTS idx_automations_trigger_tags_gin")
    op.drop_index("idx_executions_status_started", "execution_logs")
    op.drop_index("idx_executions_automation_started", "execution_logs")
    op.drop_index("idx_incidents_source_ref", "incidents")
    op.drop_index("idx_incidents_created_by_created", "incidents")
    op.drop_index("idx_incidents_status_created", "incidents")
