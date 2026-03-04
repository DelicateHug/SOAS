"""Add user_secrets table for per-user encrypted secrets.

Revision ID: 023
Revises: 022
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_secrets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_secrets_user_name"),
    )
    op.create_index("idx_user_secrets_user_id", "user_secrets", ["user_id"])

    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES
            (gen_random_uuid(), 'user_secret', 'admin_list', 'List all user secrets (names only)'),
            (gen_random_uuid(), 'user_secret', 'admin_delete', 'Delete any user secret')
        ON CONFLICT (resource, action) DO NOTHING
    """)

    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'user_secret'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("user_secrets")
    op.execute("DELETE FROM permissions WHERE resource = 'user_secret'")
