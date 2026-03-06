"""Add git_pr_url column to change_requests for GitHub PR tracking.

Revision ID: 038
Revises: 037
"""

from alembic import op
import sqlalchemy as sa

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("change_requests", sa.Column("git_pr_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("change_requests", "git_pr_url")
