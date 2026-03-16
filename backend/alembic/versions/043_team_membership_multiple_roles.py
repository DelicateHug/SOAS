"""Add team_membership_roles table for multiple roles per membership.

Revision ID: 043
Revises: 042
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create team_membership_roles junction table
    op.create_table(
        "team_membership_roles",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Migrate existing role_id data from team_memberships to team_membership_roles
    op.execute("""
        INSERT INTO team_membership_roles (user_id, team_id, role_id)
        SELECT user_id, team_id, role_id FROM team_memberships
        WHERE role_id IS NOT NULL
    """)

    # Drop the role_id column from team_memberships
    op.drop_column("team_memberships", "role_id")


def downgrade() -> None:
    # Re-add role_id column
    op.add_column(
        "team_memberships",
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=True),
    )

    # Migrate first role back
    op.execute("""
        UPDATE team_memberships tm
        SET role_id = (
            SELECT tmr.role_id FROM team_membership_roles tmr
            WHERE tmr.user_id = tm.user_id AND tmr.team_id = tm.team_id
            LIMIT 1
        )
    """)

    op.drop_table("team_membership_roles")
