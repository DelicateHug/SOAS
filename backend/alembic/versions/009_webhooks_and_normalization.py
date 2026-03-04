"""Add webhooks, webhook_logs, normalization_groups, and normalization_rules tables.

Revision ID: 009
Revises: 008
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("secret_token", sa.String(64), unique=True, nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False, server_default=sa.text("'custom'")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_severity", sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("default_tags", ARRAY(sa.String()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_received", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.create_index("idx_webhooks_secret_token", "webhooks", ["secret_token"])
    op.create_index("idx_webhooks_enabled", "webhooks", ["is_enabled"])

    op.create_table(
        "webhook_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("webhook_id", UUID(as_uuid=True), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("request_body", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("normalized_data", JSONB(), nullable=True),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("remote_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_webhook_logs_webhook_created", "webhook_logs", ["webhook_id", sa.text("created_at DESC")])

    op.create_table(
        "normalization_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.create_table(
        "normalization_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("webhook_id", UUID(as_uuid=True), sa.ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("normalization_groups.id"), nullable=False),
        sa.Column("source_path", sa.String(500), nullable=False),
        sa.Column("target_field", sa.String(200), nullable=False),
        sa.Column("transform_type", sa.String(20), nullable=False, server_default=sa.text("'direct'")),
        sa.Column("transform_config", JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("default_value", JSONB(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_normalization_rules_webhook_enabled", "normalization_rules", ["webhook_id", "is_enabled"])

    # Seed default normalization groups
    op.execute("""
        INSERT INTO normalization_groups (id, name, display_name, icon, display_order)
        VALUES
            (gen_random_uuid(), 'identity', 'Identity Fields', 'user', 1),
            (gen_random_uuid(), 'network', 'Network Fields', 'globe', 2),
            (gen_random_uuid(), 'endpoint', 'Endpoint Fields', 'monitor', 3),
            (gen_random_uuid(), 'threat', 'Threat Intel', 'shield-alert', 4),
            (gen_random_uuid(), 'timing', 'Timing Fields', 'clock', 5),
            (gen_random_uuid(), 'classification', 'Classification', 'tag', 6),
            (gen_random_uuid(), 'source', 'Source Fields', 'database', 7),
            (gen_random_uuid(), 'custom', 'Custom Fields', 'settings', 8)
        ON CONFLICT (name) DO NOTHING
    """)

    # Insert webhook and normalization RBAC permissions
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES
            (gen_random_uuid(), 'webhook', 'create', 'Create webhooks'),
            (gen_random_uuid(), 'webhook', 'read', 'View webhooks'),
            (gen_random_uuid(), 'webhook', 'update', 'Update webhooks'),
            (gen_random_uuid(), 'webhook', 'delete', 'Delete webhooks'),
            (gen_random_uuid(), 'normalization', 'create', 'Create normalization rules'),
            (gen_random_uuid(), 'normalization', 'read', 'View normalization rules'),
            (gen_random_uuid(), 'normalization', 'update', 'Update normalization rules'),
            (gen_random_uuid(), 'normalization', 'delete', 'Delete normalization rules')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant all webhook and normalization permissions to admin role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource IN ('webhook', 'normalization')
        ON CONFLICT DO NOTHING
    """)

    # Grant read permissions to soc_manager role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'soc_manager'
          AND p.resource IN ('webhook', 'normalization')
          AND p.action = 'read'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("idx_normalization_rules_webhook_enabled", table_name="normalization_rules")
    op.drop_table("normalization_rules")
    op.drop_table("normalization_groups")
    op.drop_index("idx_webhook_logs_webhook_created", table_name="webhook_logs")
    op.drop_table("webhook_logs")
    op.drop_index("idx_webhooks_enabled", table_name="webhooks")
    op.drop_index("idx_webhooks_secret_token", table_name="webhooks")
    op.drop_table("webhooks")

    op.execute("""
        DELETE FROM permissions WHERE resource IN ('webhook', 'normalization')
    """)
