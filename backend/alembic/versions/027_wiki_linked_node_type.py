"""Add linked_node_type to wiki_pages for linking wiki docs to graph node types.

Revision ID: 027
Revises: 026
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wiki_pages",
        sa.Column("linked_node_type", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_wiki_pages_linked_node_type",
        "wiki_pages",
        ["linked_node_type"],
        unique=True,
        postgresql_where=sa.text("linked_node_type IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_wiki_pages_linked_node_type", table_name="wiki_pages")
    op.drop_column("wiki_pages", "linked_node_type")
