"""Add incident_variables table.

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incident_variables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), unique=True, nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Add permissions for incident_variable CRUD
    op.execute("""
        INSERT INTO permissions (id, resource, action)
        VALUES
            (gen_random_uuid(), 'incident_variable', 'create'),
            (gen_random_uuid(), 'incident_variable', 'read'),
            (gen_random_uuid(), 'incident_variable', 'update'),
            (gen_random_uuid(), 'incident_variable', 'delete')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    # Grant all incident_variable permissions to admin role
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'incident_variable'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("incident_variables")
    op.execute("DELETE FROM permissions WHERE resource = 'incident_variable'")
