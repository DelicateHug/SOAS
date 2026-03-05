"""Add Y.js collaboration state to wiki pages.

Revision ID: 033
Revises: 032
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wiki_pages", sa.Column("yjs_state", sa.LargeBinary(), nullable=True))
    op.add_column("wiki_pages", sa.Column("active_editors", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("wiki_pages", "active_editors")
    op.drop_column("wiki_pages", "yjs_state")
