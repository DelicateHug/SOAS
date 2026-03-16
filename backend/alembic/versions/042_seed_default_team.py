"""Seed default team and migrate existing data.

Revision ID: 042
Revises: 041
"""

import sqlalchemy as sa
from alembic import op

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Find an admin user to be the team creator (first user with admin role)
    admin_row = conn.execute(
        sa.text("""
            SELECT u.id FROM users u
            JOIN user_roles ur ON ur.user_id = u.id
            JOIN roles r ON r.id = ur.role_id
            WHERE r.name = 'admin'
            ORDER BY u.created_at
            LIMIT 1
        """)
    ).first()

    if admin_row is None:
        # No users exist yet, skip seeding (will be handled on first user creation)
        return

    admin_id = admin_row[0]

    # Create the default team
    conn.execute(
        sa.text("""
            INSERT INTO teams (id, name, display_name, description, is_default, created_by)
            VALUES (gen_random_uuid(), 'default', 'Default Team', 'Default team for all users', true, :admin_id)
            ON CONFLICT (name) DO NOTHING
        """),
        {"admin_id": admin_id},
    )

    default_team_row = conn.execute(
        sa.text("SELECT id FROM teams WHERE name = 'default'")
    ).first()

    if default_team_row is None:
        return

    default_team_id = default_team_row[0]

    # Add all existing users as members of the default team
    # Use their first global role as their team role, or viewer if no role
    conn.execute(
        sa.text("""
            INSERT INTO team_memberships (user_id, team_id, role_id, team_role, added_by)
            SELECT
                u.id,
                :team_id,
                COALESCE(
                    (SELECT ur.role_id FROM user_roles ur WHERE ur.user_id = u.id LIMIT 1),
                    (SELECT r.id FROM roles r WHERE r.name = 'viewer' LIMIT 1)
                ),
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM user_roles ur
                        JOIN roles r ON r.id = ur.role_id
                        WHERE ur.user_id = u.id AND r.name = 'admin'
                    ) THEN 'owner'
                    ELSE 'member'
                END,
                :admin_id
            FROM users u
            ON CONFLICT (user_id, team_id) DO NOTHING
        """),
        {"team_id": default_team_id, "admin_id": admin_id},
    )

    # Assign existing incidents, cases, automations to default team
    for table in ("incidents", "cases", "automations"):
        conn.execute(
            sa.text(f"UPDATE {table} SET team_id = :team_id WHERE team_id IS NULL"),
            {"team_id": default_team_id},
        )

    # Wiki pages are intentionally left with team_id = NULL (global)


def downgrade() -> None:
    conn = op.get_bind()

    # Clear team assignments
    for table in ("incidents", "cases", "automations"):
        conn.execute(sa.text(f"UPDATE {table} SET team_id = NULL"))

    conn.execute(sa.text("DELETE FROM team_memberships"))
    conn.execute(sa.text("DELETE FROM teams WHERE is_default = true"))
