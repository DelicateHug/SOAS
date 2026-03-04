"""Add SOAS application-level variables with role-based permissions.

Revision ID: 005
Revises: 004
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "soas_variables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value", JSONB(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "soas_variable_permissions",
        sa.Column("variable_id", UUID(as_uuid=True), sa.ForeignKey("soas_variables.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("can_read", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # Insert the new soas_variable permissions into the permissions table
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES
            (gen_random_uuid(), 'soas_variable', 'create', 'Create SOAS variables'),
            (gen_random_uuid(), 'soas_variable', 'read', 'View SOAS variables'),
            (gen_random_uuid(), 'soas_variable', 'update', 'Update SOAS variables'),
            (gen_random_uuid(), 'soas_variable', 'delete', 'Delete SOAS variables')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant all soas_variable permissions to admin role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'soas_variable'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("soas_variable_permissions")
    op.drop_table("soas_variables")

    op.execute("""
        DELETE FROM permissions WHERE resource = 'soas_variable'
    """)
