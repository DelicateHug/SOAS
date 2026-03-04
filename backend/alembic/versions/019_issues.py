"""Issues: core tables, links, notes, checklist, and RBAC permissions.

Revision ID: 019
Revises: 018
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- issues ---
    op.create_table(
        "issues",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("graph_annotation", postgresql.JSONB(), nullable=True),
    )
    op.create_index("idx_issues_status", "issues", ["status"])
    op.create_index("idx_issues_assigned_to", "issues", ["assigned_to"])
    op.create_index("idx_issues_created_by", "issues", ["created_by"])

    # --- issue_links ---
    op.create_table(
        "issue_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "issue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint(
            "issue_id", "target_type", "target_id", name="uq_issue_link_unique"
        ),
    )
    op.create_index("idx_issue_links_issue", "issue_links", ["issue_id"])
    op.create_index(
        "idx_issue_links_target", "issue_links", ["target_type", "target_id"]
    )

    # --- issue_notes ---
    op.create_table(
        "issue_notes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "issue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_evidence", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_issue_notes_issue", "issue_notes", ["issue_id"])
    op.create_index(
        "idx_issue_notes_evidence", "issue_notes", ["issue_id", "is_evidence"]
    )

    # --- issue_checklist_items ---
    op.create_table(
        "issue_checklist_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "issue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.String(500), nullable=False),
        sa.Column("is_checked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_issue_checklist_issue", "issue_checklist_items", ["issue_id"]
    )

    # --- Seed RBAC permissions ---
    op.execute(
        """
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'issue', 'create', 'Create new issues'),
            (gen_random_uuid(), 'issue', 'read',   'View issues'),
            (gen_random_uuid(), 'issue', 'update', 'Update issues'),
            (gen_random_uuid(), 'issue', 'delete', 'Delete issues')
        ON CONFLICT (resource, action) DO NOTHING
        """
    )

    # Grant all issue permissions to admin and soc_manager
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('admin', 'soc_manager')
          AND p.resource = 'issue'
        ON CONFLICT DO NOTHING
        """
    )

    # Grant issue:read and issue:create to analyst roles
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3')
          AND p.resource = 'issue'
          AND p.action IN ('read', 'create')
        ON CONFLICT DO NOTHING
        """
    )

    # Grant issue:read to viewer
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'viewer'
          AND p.resource = 'issue'
          AND p.action = 'read'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove role_permissions for issue permissions
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'issue'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE resource = 'issue'")

    op.drop_index("idx_issue_checklist_issue", table_name="issue_checklist_items")
    op.drop_table("issue_checklist_items")

    op.drop_index("idx_issue_notes_evidence", table_name="issue_notes")
    op.drop_index("idx_issue_notes_issue", table_name="issue_notes")
    op.drop_table("issue_notes")

    op.drop_index("idx_issue_links_target", table_name="issue_links")
    op.drop_index("idx_issue_links_issue", table_name="issue_links")
    op.drop_table("issue_links")

    op.drop_index("idx_issues_created_by", table_name="issues")
    op.drop_index("idx_issues_assigned_to", table_name="issues")
    op.drop_index("idx_issues_status", table_name="issues")
    op.drop_table("issues")
