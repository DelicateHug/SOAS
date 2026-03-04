"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_secret", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # --- WebAuthn Credentials ---
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("transports", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("device_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # --- Refresh Tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_info", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # --- Roles ---
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # --- Permissions ---
    op.create_table(
        "permissions",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

    # --- Role Permissions (M2M) ---
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("permission_id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
    )

    # --- User Roles (M2M) ---
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
    )

    # --- Incidents ---
    op.create_table(
        "incidents",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'detected'")),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lead_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )
    op.create_index("idx_incidents_severity", "incidents", ["severity"])
    op.create_index("idx_incidents_status", "incidents", ["status"])
    op.create_index("idx_incidents_created", "incidents", [sa.text("created_at DESC")])

    # --- Incident Assignments ---
    op.create_table(
        "incident_assignments",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_in_incident", sa.String(100), nullable=False, server_default=sa.text("'responder'")),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "user_id", name="uq_incident_assignment_user"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"]),
    )

    # --- Cases ---
    op.create_table(
        "cases",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'open'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["lead_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )

    # --- Case Incidents (M2M) ---
    op.create_table(
        "case_incidents",
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("linked_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("case_id", "incident_id"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_by"], ["users.id"]),
    )

    # --- Automations ---
    op.create_table(
        "automations",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("graph_file", sa.String(500), nullable=True),
        sa.Column("graph_data", postgresql.JSONB(), nullable=True),
        sa.Column("script_hash", sa.String(128), nullable=True),
        sa.Column("script_path", sa.String(500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("parameters", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("300")),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
    )

    # --- Automation Permissions ---
    op.create_table(
        "automation_permissions",
        sa.Column("automation_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("can_execute", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("automation_id", "role_id"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
    )

    # --- Execution Logs ---
    op.create_table(
        "execution_logs",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("automation_id", sa.UUID(), nullable=False),
        sa.Column("triggered_by", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("worker_id", sa.String(255), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("result_data", postgresql.JSONB(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"]),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
    )
    op.create_index("idx_executions_automation", "execution_logs", ["automation_id"])
    op.create_index("idx_executions_status", "execution_logs", ["status"])
    op.create_index("idx_executions_created", "execution_logs", [sa.text("created_at DESC")])

    # --- Timeline Entries ---
    op.create_table(
        "timeline_entries",
        sa.Column("id", sa.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.CheckConstraint(
            "incident_id IS NOT NULL OR case_id IS NOT NULL",
            name="timeline_has_parent",
        ),
    )
    op.create_index(
        "idx_timeline_incident",
        "timeline_entries",
        ["incident_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_timeline_case",
        "timeline_entries",
        ["case_id", sa.text("created_at DESC")],
    )

    # --- Seed system roles ---
    op.execute("""
        INSERT INTO roles (id, name, display_name, description, is_system) VALUES
            (gen_random_uuid(), 'admin',          'Administrator',    'Full system access',                     true),
            (gen_random_uuid(), 'soc_manager',    'SOC Manager',      'Manage analysts, review cases',          true),
            (gen_random_uuid(), 'soc_analyst_l3', 'SOC Analyst L3',   'Senior analyst, run any automation',     true),
            (gen_random_uuid(), 'soc_analyst_l2', 'SOC Analyst L2',   'Mid analyst, run approved automations',  true),
            (gen_random_uuid(), 'soc_analyst_l1', 'SOC Analyst L1',   'Junior analyst, triage and observe',     true),
            (gen_random_uuid(), 'viewer',         'Viewer',           'Read-only access',                       true)
        ON CONFLICT (name) DO NOTHING
    """)

    # --- Seed permissions ---
    op.execute("""
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'user',       'create',  'Create users'),
            (gen_random_uuid(), 'user',       'read',    'View users'),
            (gen_random_uuid(), 'user',       'update',  'Update users'),
            (gen_random_uuid(), 'user',       'delete',  'Delete users'),
            (gen_random_uuid(), 'role',       'create',  'Create roles'),
            (gen_random_uuid(), 'role',       'read',    'View roles'),
            (gen_random_uuid(), 'role',       'update',  'Update roles'),
            (gen_random_uuid(), 'role',       'delete',  'Delete roles'),
            (gen_random_uuid(), 'incident',   'create',  'Create incidents'),
            (gen_random_uuid(), 'incident',   'read',    'View incidents'),
            (gen_random_uuid(), 'incident',   'update',  'Update incidents'),
            (gen_random_uuid(), 'incident',   'delete',  'Delete incidents'),
            (gen_random_uuid(), 'incident',   'assign',  'Assign users to incidents'),
            (gen_random_uuid(), 'incident',   'close',   'Close incidents'),
            (gen_random_uuid(), 'case',       'create',  'Create cases'),
            (gen_random_uuid(), 'case',       'read',    'View cases'),
            (gen_random_uuid(), 'case',       'update',  'Update cases'),
            (gen_random_uuid(), 'case',       'delete',  'Delete cases'),
            (gen_random_uuid(), 'case',       'close',   'Close cases'),
            (gen_random_uuid(), 'automation', 'create',  'Create automations'),
            (gen_random_uuid(), 'automation', 'read',    'View automations'),
            (gen_random_uuid(), 'automation', 'update',  'Update automations'),
            (gen_random_uuid(), 'automation', 'delete',  'Delete automations'),
            (gen_random_uuid(), 'automation', 'execute', 'Execute automations'),
            (gen_random_uuid(), 'execution',  'read',    'View execution logs'),
            (gen_random_uuid(), 'execution',  'cancel',  'Cancel running executions'),
            (gen_random_uuid(), 'timeline',   'create',  'Create timeline entries'),
            (gen_random_uuid(), 'timeline',   'read',    'View timeline entries'),
            (gen_random_uuid(), 'dashboard',  'read',    'View dashboard'),
            (gen_random_uuid(), 'admin',      'access',  'Access admin panel')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # --- Assign permissions to roles ---
    # Admin: all permissions
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'admin'
        ON CONFLICT DO NOTHING
    """)

    # SOC Manager: everything except role management and admin
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_manager'
          AND NOT (p.resource = 'role' AND p.action IN ('create', 'update', 'delete'))
          AND NOT (p.resource = 'admin')
        ON CONFLICT DO NOTHING
    """)

    # SOC Analyst L3
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l3'
          AND p.resource IN ('incident', 'case', 'automation', 'execution', 'timeline', 'dashboard')
        ON CONFLICT DO NOTHING
    """)

    # SOC Analyst L2
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l2'
          AND (
            (p.resource = 'incident' AND p.action IN ('create', 'read', 'update', 'assign'))
            OR (p.resource = 'case' AND p.action IN ('create', 'read', 'update'))
            OR (p.resource = 'automation' AND p.action IN ('read', 'execute'))
            OR (p.resource = 'execution' AND p.action = 'read')
            OR (p.resource = 'timeline' AND p.action IN ('create', 'read'))
            OR (p.resource = 'dashboard' AND p.action = 'read')
          )
        ON CONFLICT DO NOTHING
    """)

    # SOC Analyst L1
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_analyst_l1'
          AND (
            (p.resource = 'incident' AND p.action IN ('create', 'read'))
            OR (p.resource = 'case' AND p.action = 'read')
            OR (p.resource = 'automation' AND p.action = 'read')
            OR (p.resource = 'execution' AND p.action = 'read')
            OR (p.resource = 'timeline' AND p.action = 'read')
            OR (p.resource = 'dashboard' AND p.action = 'read')
          )
        ON CONFLICT DO NOTHING
    """)

    # Viewer: read-only
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'viewer'
          AND p.action = 'read'
          AND p.resource IN ('incident', 'case', 'automation', 'execution', 'timeline', 'dashboard')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("timeline_entries")
    op.drop_table("execution_logs")
    op.drop_table("automation_permissions")
    op.drop_table("automations")
    op.drop_table("case_incidents")
    op.drop_table("cases")
    op.drop_table("incident_assignments")
    op.drop_table("incidents")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("refresh_tokens")
    op.drop_table("webauthn_credentials")
    op.drop_table("users")
