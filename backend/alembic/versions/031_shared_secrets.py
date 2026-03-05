"""Add shared secret columns and permissions table.

Revision ID: 031
Revises: 030
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sharing columns to user_secrets
    op.add_column(
        "user_secrets",
        sa.Column("is_shared", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "user_secrets",
        sa.Column("server_encrypted_value", sa.Text(), nullable=True),
    )

    # Create shared_secret_permissions table
    op.create_table(
        "shared_secret_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("secret_id", UUID(as_uuid=True), sa.ForeignKey("user_secrets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_read", sa.Boolean(), server_default="true", nullable=False),
        sa.UniqueConstraint("secret_id", "role_id", name="uq_shared_secret_perm_secret_role"),
    )
    op.create_index("ix_shared_secret_perm_role", "shared_secret_permissions", ["role_id"])


def downgrade() -> None:
    op.drop_index("ix_shared_secret_perm_role", table_name="shared_secret_permissions")
    op.drop_table("shared_secret_permissions")
    op.drop_column("user_secrets", "server_encrypted_value")
    op.drop_column("user_secrets", "is_shared")
