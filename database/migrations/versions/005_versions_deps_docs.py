"""Version control, dependency tracking, and automation documentation.

Revision ID: 005
Revises: 004
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Add documentation column to automations ---
    op.add_column(
        "automations",
        sa.Column("documentation", sa.Text(), nullable=True),
    )

    # --- automation_dependencies ---
    op.create_table(
        "automation_dependencies",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "automation_id",
            sa.UUID(),
            sa.ForeignKey("automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dependency_type", sa.String(20), nullable=False),
        sa.Column("dependency_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "automation_id", "dependency_type", "dependency_id",
            name="uq_auto_deps_unique",
        ),
    )
    op.create_index(
        "idx_auto_deps_automation",
        "automation_dependencies",
        ["automation_id"],
    )
    op.create_index(
        "idx_auto_deps_dependency",
        "automation_dependencies",
        ["dependency_type", "dependency_id"],
    )

    # --- automation_versions ---
    op.create_table(
        "automation_versions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "automation_id",
            sa.UUID(),
            sa.ForeignKey("automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "graph_data",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("trigger_tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_trigger_enabled", sa.Boolean(), nullable=True),
        sa.Column("documentation", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "automation_id", "version_number",
            name="uq_auto_version_number",
        ),
    )
    op.create_index(
        "idx_auto_versions_lookup",
        "automation_versions",
        ["automation_id", sa.text("version_number DESC")],
    )

    # --- code_library_block_versions ---
    op.create_table(
        "code_library_block_versions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "block_id",
            sa.UUID(),
            sa.ForeignKey("code_library_blocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("input_ports", postgresql.JSONB(), nullable=True),
        sa.Column("output_ports", postgresql.JSONB(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "block_id", "version_number",
            name="uq_code_version_number",
        ),
    )
    op.create_index(
        "idx_code_versions_lookup",
        "code_library_block_versions",
        ["block_id", sa.text("version_number DESC")],
    )

    # --- scheduled_job_versions ---
    op.create_table(
        "scheduled_job_versions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            sa.UUID(),
            sa.ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_type", sa.String(20), nullable=True),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("calendar_config", postgresql.JSONB(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "version_number",
            name="uq_job_version_number",
        ),
    )
    op.create_index(
        "idx_job_versions_lookup",
        "scheduled_job_versions",
        ["job_id", sa.text("version_number DESC")],
    )


def downgrade() -> None:
    op.drop_table("scheduled_job_versions")
    op.drop_table("code_library_block_versions")
    op.drop_table("automation_versions")
    op.drop_table("automation_dependencies")
    op.drop_column("automations", "documentation")
