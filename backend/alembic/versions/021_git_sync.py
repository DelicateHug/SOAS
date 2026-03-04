"""Git sync: sync log table, settings seeds, RBAC permissions.

Revision ID: 021
Revises: 020
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- git_sync_logs ---
    op.create_table(
        "git_sync_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("sync_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("entities_pushed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entities_pulled", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conflicts", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_git_sync_logs_created", "git_sync_logs", ["created_at"])
    op.create_index("idx_git_sync_logs_status", "git_sync_logs", ["status"])

    # --- Seed app_settings for git sync ---
    op.execute(
        """
        INSERT INTO app_settings (key, value, description) VALUES
            ('git_sync_enabled',          'false',
             'Enable Git-based persistence sync'),
            ('git_sync_remote_url',       '',
             'Remote Git repository URL'),
            ('git_sync_branch',           'main',
             'Git branch to sync with'),
            ('git_sync_interval_seconds', '300',
             'Sync interval in seconds (minimum 300)'),
            ('git_sync_auth_type',        'token',
             'Authentication type: token or ssh_key'),
            ('git_sync_auth_token',       '',
             'Personal access token for Git auth'),
            ('git_sync_ssh_key_path',     '',
             'Path to SSH private key for Git auth'),
            ('git_sync_entity_types',     'automations,wiki,code_library,settings,roles,form_definitions,variables,normalization,webhook_sources,incident_variables',
             'Comma-separated entity types to sync')
        ON CONFLICT (key) DO NOTHING
        """
    )

    # --- Seed RBAC permissions ---
    op.execute(
        """
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'git_sync', 'read',  'View git sync status and logs'),
            (gen_random_uuid(), 'git_sync', 'admin', 'Configure and trigger git sync')
        ON CONFLICT (resource, action) DO NOTHING
        """
    )

    # Grant git_sync permissions to admin and soc_manager
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('admin', 'soc_manager')
          AND p.resource = 'git_sync'
        ON CONFLICT DO NOTHING
        """
    )

    # Grant git_sync:read to analyst roles
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3')
          AND p.resource = 'git_sync'
          AND p.action = 'read'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove role_permissions for git_sync permissions
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'git_sync'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE resource = 'git_sync'")

    # Remove git sync settings
    op.execute(
        "DELETE FROM app_settings WHERE key LIKE 'git_sync_%'"
    )

    op.drop_index("idx_git_sync_logs_status", table_name="git_sync_logs")
    op.drop_index("idx_git_sync_logs_created", table_name="git_sync_logs")
    op.drop_table("git_sync_logs")
