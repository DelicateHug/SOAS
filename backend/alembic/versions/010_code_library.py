"""Code Library tables for reusable custom code blocks.

Revision ID: 010
Revises: 009
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- code_library_blocks ---
    op.create_table(
        "code_library_blocks",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("code", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(20), nullable=False, server_default="python"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- code_library_permissions ---
    op.create_table(
        "code_library_permissions",
        sa.Column("block_id", sa.UUID(), sa.ForeignKey("code_library_blocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.UUID(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("can_read", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("can_edit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("can_use", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("block_id", "role_id"),
    )

    # --- code_library_favorites ---
    op.create_table(
        "code_library_favorites",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_id", sa.UUID(), sa.ForeignKey("code_library_blocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "block_id"),
    )

    # --- code_library_user_categories ---
    op.create_table(
        "code_library_user_categories",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.UUID(), sa.ForeignKey("code_library_user_categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- code_library_user_block_assignments ---
    op.create_table(
        "code_library_user_block_assignments",
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_id", sa.UUID(), sa.ForeignKey("code_library_blocks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.UUID(), sa.ForeignKey("code_library_user_categories.id", ondelete="SET NULL"), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "block_id"),
    )

    # Seed code_library permissions into the permissions table
    op.execute("""
        INSERT INTO permissions (id, resource, action)
        VALUES
            (gen_random_uuid(), 'code_library', 'create'),
            (gen_random_uuid(), 'code_library', 'read'),
            (gen_random_uuid(), 'code_library', 'update'),
            (gen_random_uuid(), 'code_library', 'delete')
        ON CONFLICT DO NOTHING
    """)

    # Grant code_library:read and code_library:create to all existing roles
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE p.resource = 'code_library' AND p.action IN ('read', 'create')
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("code_library_user_block_assignments")
    op.drop_table("code_library_user_categories")
    op.drop_table("code_library_favorites")
    op.drop_table("code_library_permissions")
    op.drop_table("code_library_blocks")

    op.execute("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'code_library'
        )
    """)
    op.execute("DELETE FROM permissions WHERE resource = 'code_library'")
