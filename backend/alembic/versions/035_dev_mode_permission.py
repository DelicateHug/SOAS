"""Add deployment:dev_mode permission for per-user dev mode access.

Revision ID: 035
Revises: 034
Create Date: 2026-03-05
"""

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the deployment:dev_mode permission
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES (gen_random_uuid(), 'deployment', 'dev_mode', 'Switch to development mode (allows editing)')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Assign to admin role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'deployment' AND p.action = 'dev_mode'
        ON CONFLICT DO NOTHING
    """)

    # Assign to soc_manager role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'soc_manager'
          AND p.resource = 'deployment' AND p.action = 'dev_mode'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'deployment' AND action = 'dev_mode'
        )
    """)
    op.execute("DELETE FROM permissions WHERE resource = 'deployment' AND action = 'dev_mode'")
