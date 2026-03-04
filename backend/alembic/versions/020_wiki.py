"""Wiki: pages, versions, permissions, full-text search index, and RBAC seeds.

Revision ID: 020
Revises: 019
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- wiki_pages ---
    op.create_table(
        "wiki_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), nullable=False, unique=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(20), server_default="published", nullable=False
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
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
    op.create_index("idx_wiki_pages_slug", "wiki_pages", ["slug"], unique=True)
    op.create_index("idx_wiki_pages_parent", "wiki_pages", ["parent_id"])
    op.create_index(
        "idx_wiki_pages_tags", "wiki_pages", ["tags"], postgresql_using="gin"
    )
    op.execute(
        """
        CREATE INDEX idx_wiki_pages_fts ON wiki_pages
        USING gin (to_tsvector('english', title || ' ' || coalesce(content, '')))
        """
    )

    # --- wiki_page_versions ---
    op.create_table(
        "wiki_page_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("change_summary", sa.String(500), nullable=True),
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
        sa.UniqueConstraint(
            "page_id", "version_number", name="uq_wiki_page_version_number"
        ),
    )
    op.create_index(
        "idx_wiki_page_versions_page", "wiki_page_versions", ["page_id"]
    )

    # --- wiki_page_permissions ---
    op.create_table(
        "wiki_page_permissions",
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "can_read", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column(
            "can_edit", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # --- Seed RBAC permissions ---
    op.execute(
        """
        INSERT INTO permissions (id, resource, action, description) VALUES
            (gen_random_uuid(), 'wiki', 'create', 'Create wiki pages'),
            (gen_random_uuid(), 'wiki', 'read',   'View wiki pages'),
            (gen_random_uuid(), 'wiki', 'update', 'Edit wiki pages'),
            (gen_random_uuid(), 'wiki', 'delete', 'Delete wiki pages')
        ON CONFLICT (resource, action) DO NOTHING
        """
    )

    # Grant all wiki permissions to admin and soc_manager
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('admin', 'soc_manager')
          AND p.resource = 'wiki'
        ON CONFLICT DO NOTHING
        """
    )

    # Grant wiki:read, wiki:create, wiki:update to analyst roles
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name IN ('soc_analyst_l1', 'soc_analyst_l2', 'soc_analyst_l3')
          AND p.resource = 'wiki'
          AND p.action IN ('read', 'create', 'update')
        ON CONFLICT DO NOTHING
        """
    )

    # Grant wiki:read to viewer
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'viewer'
          AND p.resource = 'wiki'
          AND p.action = 'read'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove role_permissions for wiki permissions
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE resource = 'wiki'
        )
        """
    )
    op.execute("DELETE FROM permissions WHERE resource = 'wiki'")

    op.drop_table("wiki_page_permissions")

    op.drop_index("idx_wiki_page_versions_page", table_name="wiki_page_versions")
    op.drop_table("wiki_page_versions")

    op.execute("DROP INDEX IF EXISTS idx_wiki_pages_fts")
    op.drop_index("idx_wiki_pages_tags", table_name="wiki_pages")
    op.drop_index("idx_wiki_pages_parent", table_name="wiki_pages")
    op.drop_index("idx_wiki_pages_slug", table_name="wiki_pages")
    op.drop_table("wiki_pages")
