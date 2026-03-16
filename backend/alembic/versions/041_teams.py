"""Add teams, team_memberships tables and team_id columns to incidents, cases, automations, wiki_pages.

Revision ID: 041
Revises: 040
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- teams table ---
    op.create_table(
        "teams",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- team_memberships table ---
    op.create_table(
        "team_memberships",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("team_role", sa.String(20), nullable=False, server_default=sa.text("'member'")),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("added_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # --- Add team_id FK to existing tables ---
    for table in ("incidents", "cases", "automations", "wiki_pages"):
        op.add_column(
            table,
            sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index(f"idx_{table}_team_id", table, ["team_id"])

    # --- Add team permissions ---
    conn = op.get_bind()
    team_perms = [
        ("team", "read", "View teams"),
        ("team", "create", "Create teams"),
        ("team", "update", "Update team details"),
        ("team", "delete", "Delete teams"),
        ("team", "manage_members", "Add/remove team members"),
    ]
    for resource, action, description in team_perms:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, resource, action, description) "
                "VALUES (gen_random_uuid(), :resource, :action, :description) "
                "ON CONFLICT (resource, action) DO NOTHING"
            ),
            {"resource": resource, "action": action, "description": description},
        )

    # Grant all team permissions to admin (via CROSS JOIN already handles this)
    # Grant team:read, team:create, team:update, team:manage_members to soc_manager
    conn.execute(
        sa.text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name = 'soc_manager'
              AND p.resource = 'team'
              AND p.action IN ('read', 'create', 'update', 'manage_members')
            ON CONFLICT DO NOTHING
        """)
    )

    # Grant team:read to all analyst roles and viewer
    conn.execute(
        sa.text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name IN ('soc_analyst_l3', 'soc_analyst_l2', 'soc_analyst_l1', 'viewer')
              AND p.resource = 'team'
              AND p.action = 'read'
            ON CONFLICT DO NOTHING
        """)
    )


def downgrade() -> None:
    for table in ("incidents", "cases", "automations", "wiki_pages"):
        op.drop_index(f"idx_{table}_team_id", table_name=table)
        op.drop_column(table, "team_id")
    op.drop_table("team_memberships")
    op.drop_table("teams")

    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM permissions WHERE resource = 'team'")
    )
