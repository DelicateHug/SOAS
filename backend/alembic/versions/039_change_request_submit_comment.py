"""Add submit_comment column to change_requests.

Revision ID: 039
Revises: 038
"""

from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("change_requests", sa.Column("submit_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("change_requests", "submit_comment")
