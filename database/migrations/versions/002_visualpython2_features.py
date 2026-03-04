"""VisualPython2 features: trigger tags, automation trigger log.

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
    # --- Add trigger_tags and is_trigger_enabled to automations ---
    op.add_column(
        "automations",
        sa.Column(
            "trigger_tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=True,
        ),
    )
    op.add_column(
        "automations",
        sa.Column(
            "is_trigger_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # --- GIN index on automations.trigger_tags ---
    op.execute(
        "CREATE INDEX idx_automations_trigger_tags ON automations USING GIN (trigger_tags)"
    )

    # --- GIN index on incidents.tags (if not exists) ---
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_tags ON incidents USING GIN (tags)"
    )

    # --- Automation Trigger Log ---
    op.create_table(
        "automation_trigger_log",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("automation_id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=True),
        sa.Column(
            "matched_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'triggered'"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["execution_id"], ["execution_logs.id"]),
    )
    op.create_index(
        "idx_trigger_log_automation", "automation_trigger_log", ["automation_id"]
    )
    op.create_index(
        "idx_trigger_log_incident", "automation_trigger_log", ["incident_id"]
    )

    # --- Seed new permissions for graph_editor ---
    op.execute("""
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'graph_editor', 'access',   'Access the graph editor'),
            (gen_random_uuid(), 'graph_editor', 'test_run', 'Run test executions from the graph editor')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant graph_editor permissions to admin (all), soc_manager, soc_analyst_l3
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'graph_editor'
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name IN ('soc_manager', 'soc_analyst_l3')
          AND p.resource = 'graph_editor'
        ON CONFLICT DO NOTHING
    """)
    # L2 gets access but not test_run
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l2'
          AND p.resource = 'graph_editor'
          AND p.action = 'access'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("automation_trigger_log")
    op.drop_column("automations", "is_trigger_enabled")
    op.drop_column("automations", "trigger_tags")
    op.execute("DROP INDEX IF EXISTS idx_incidents_tags")
    op.execute("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'graph_editor'
        )
    """)
    op.execute("DELETE FROM permissions WHERE resource = 'graph_editor'")
