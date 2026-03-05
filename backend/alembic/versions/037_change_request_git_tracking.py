"""Add git tracking columns to change_requests.

Revision ID: 037
Revises: 036
"""

from alembic import op
import sqlalchemy as sa

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("change_requests", sa.Column("git_branch", sa.String(200), nullable=True))
    op.add_column("change_requests", sa.Column("git_sha", sa.String(40), nullable=True))
    op.add_column(
        "change_requests",
        sa.Column("target_tier", sa.String(10), server_default="dev", nullable=False),
    )

    # Drop old partial unique index and recreate with pushed_to_dev status
    op.drop_index("ix_cr_active_per_user", table_name="change_requests")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_cr_active_per_user
        ON change_requests (created_by, entity_type, entity_id)
        WHERE status IN ('draft', 'submitted', 'pushed_to_dev')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_cr_active_per_user", table_name="change_requests")
    op.execute(
        """
        CREATE UNIQUE INDEX ix_cr_active_per_user
        ON change_requests (created_by, entity_type, entity_id)
        WHERE status IN ('draft', 'submitted')
        """
    )
    op.drop_column("change_requests", "target_tier")
    op.drop_column("change_requests", "git_sha")
    op.drop_column("change_requests", "git_branch")
