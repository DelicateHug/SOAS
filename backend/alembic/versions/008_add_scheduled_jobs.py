"""Add scheduled_jobs table for cron-like automation execution.

Revision ID: 008
Revises: 007
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("automation_id", UUID(as_uuid=True), sa.ForeignKey("automations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("calendar_config", JSONB(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("parameters", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_scheduled_jobs_next_run", "scheduled_jobs", ["is_enabled", "next_run_at"])
    op.create_index("idx_scheduled_jobs_automation", "scheduled_jobs", ["automation_id"])

    # Insert job RBAC permissions
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES
            (gen_random_uuid(), 'job', 'create', 'Create scheduled jobs'),
            (gen_random_uuid(), 'job', 'read', 'View scheduled jobs'),
            (gen_random_uuid(), 'job', 'update', 'Update scheduled jobs'),
            (gen_random_uuid(), 'job', 'delete', 'Delete scheduled jobs')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant all job permissions to admin and soc_manager roles
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('admin', 'soc_manager')
          AND p.resource = 'job'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_scheduled_jobs_automation", table_name="scheduled_jobs")
    op.drop_index("idx_scheduled_jobs_next_run", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")

    op.execute("""
        DELETE FROM permissions WHERE resource = 'job'
    """)
