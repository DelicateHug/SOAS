"""Monitoring, alerting, and quorum tables with default permissions and seed data.

Revision ID: 004
Revises: 003
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- health_metric_snapshots ---
    op.create_table(
        "health_metric_snapshots",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("component_type", sa.String(50), nullable=False),
        sa.Column("component_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_health_snapshots_component",
        "health_metric_snapshots",
        ["component_type", "component_id"],
    )
    op.create_index(
        "idx_health_snapshots_recorded",
        "health_metric_snapshots",
        [sa.text("recorded_at DESC")],
    )
    op.create_index(
        "idx_health_snapshots_type_time",
        "health_metric_snapshots",
        ["component_type", sa.text("recorded_at DESC")],
    )

    # --- alert_rules ---
    op.create_table(
        "alert_rules",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("component_type", sa.String(50), nullable=False),
        sa.Column("metric_key", sa.String(100), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default=sa.text("300")),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("idx_alert_rules_component", "alert_rules", ["component_type"])

    # --- alerts ---
    op.create_table(
        "alerts",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("rule_id", sa.UUID(), nullable=True),
        sa.Column("component_type", sa.String(50), nullable=False),
        sa.Column("component_id", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("acknowledged_by", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
    )
    op.create_index("idx_alerts_status", "alerts", ["status"])
    op.create_index("idx_alerts_severity", "alerts", ["severity"])
    op.create_index(
        "idx_alerts_created",
        "alerts",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_alerts_component",
        "alerts",
        ["component_type", "component_id"],
    )

    # --- monitoring_agents ---
    op.create_table(
        "monitoring_agents",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("component_type", sa.String(50), nullable=False),
        sa.Column("check_interval_seconds", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Seed monitoring permissions ---
    op.execute("""
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'monitoring', 'read',  'View monitoring dashboard and health data'),
            (gen_random_uuid(), 'monitoring', 'admin', 'Configure monitoring alerts and agents')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant monitoring permissions to admin role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'monitoring'
        ON CONFLICT DO NOTHING
    """)

    # Grant monitoring:read to soc_manager
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_manager'
          AND p.resource = 'monitoring'
          AND p.action = 'read'
        ON CONFLICT DO NOTHING
    """)

    # --- Seed default monitoring agents ---
    op.execute("""
        INSERT INTO monitoring_agents (id, name, description, component_type, check_interval_seconds) VALUES
            (gen_random_uuid(), 'api_checker',       'Checks API health and response time',       'api',           30),
            (gen_random_uuid(), 'postgres_checker',  'Checks PostgreSQL connectivity and stats',  'postgres',      30),
            (gen_random_uuid(), 'redis_checker',     'Checks Redis memory and connectivity',      'redis',         30),
            (gen_random_uuid(), 'celery_checker',    'Checks Celery worker health and queues',    'celery_worker', 30),
            (gen_random_uuid(), 'beat_checker',      'Checks Celery Beat schedule health',        'celery_beat',   60),
            (gen_random_uuid(), 'websocket_checker', 'Checks active WebSocket connections',       'websocket',     30)
        ON CONFLICT (name) DO NOTHING
    """)

    # --- Seed default alert rules ---
    # Use the first admin user as created_by (required FK)
    op.execute("""
        INSERT INTO alert_rules (id, name, description, component_type, metric_key, condition, threshold, severity, cooldown_seconds, created_by)
        SELECT
            gen_random_uuid(),
            v.name,
            v.description,
            v.component_type,
            v.metric_key,
            v.condition,
            v.threshold,
            v.severity,
            v.cooldown,
            (SELECT u.id FROM users u LIMIT 1)
        FROM (VALUES
            ('High API Response Time',    'API response time exceeds 1 second',         'api',           'response_time_ms',    'gt',  1000, 'warning',  300),
            ('API Unhealthy',             'API health check failed',                    'api',           'response_time_ms',    'gt',  5000, 'critical', 120),
            ('No Celery Workers',         'No Celery workers are alive',                'celery_worker', 'alive_workers',       'lte', 0,    'critical', 60),
            ('High Redis Memory',         'Redis memory usage exceeds 500 MB',          'redis',         'memory_mb',           'gt',  500,  'warning',  600),
            ('High Queue Depth',          'Total task queue depth exceeds 100',         'celery_worker', 'total_queue_depth',   'gt',  100,  'warning',  300),
            ('High DB Connections',       'PostgreSQL active connections exceed 50',    'postgres',      'active_connections',  'gt',  50,   'warning',  300)
        ) AS v(name, description, component_type, metric_key, condition, threshold, severity, cooldown)
        WHERE EXISTS (SELECT 1 FROM users LIMIT 1)
    """)


def downgrade() -> None:
    op.drop_table("monitoring_agents")
    op.drop_table("alerts")
    op.drop_table("alert_rules")
    op.drop_table("health_metric_snapshots")

    # Remove monitoring permissions
    op.execute("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'monitoring'
        )
    """)
    op.execute("DELETE FROM permissions WHERE resource = 'monitoring'")
