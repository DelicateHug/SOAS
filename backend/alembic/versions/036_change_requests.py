"""Add change_requests table for dev/prod draft workflow.

Revision ID: 036
Revises: 035
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_requests",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("snapshot", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("diff_summary", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("review_comment", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # One active draft/submission per user per entity
    op.execute("""
        CREATE UNIQUE INDEX ix_cr_active_per_user
        ON change_requests (created_by, entity_type, entity_id)
        WHERE status IN ('draft', 'submitted')
    """)

    op.create_index("ix_change_requests_status", "change_requests", ["status"])
    op.create_index("ix_change_requests_created_by", "change_requests", ["created_by"])

    # Add change_request:review permission for admins
    op.execute("""
        INSERT INTO permissions (id, resource, action, description)
        VALUES (gen_random_uuid(), 'change_request', 'review', 'Review and approve/reject change requests')
        ON CONFLICT (resource, action) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'admin'
          AND p.resource = 'change_request' AND p.action = 'review'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'change_request' AND action = 'review'
        )
    """)
    op.execute("DELETE FROM permissions WHERE resource = 'change_request' AND action = 'review'")
    op.drop_table("change_requests")
