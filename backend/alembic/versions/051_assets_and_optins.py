"""Phase 6: assets + user_run_optins.

Revision ID: 051
Revises: 050
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("identifier", sa.String(500), nullable=False),
        sa.Column("label", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("asset_type", "identifier", name="uq_assets_type_identifier"),
    )
    op.create_index("idx_assets_type", "assets", ["asset_type"])
    op.create_index("idx_assets_team", "assets", ["team_id"])

    op.create_table(
        "user_run_optins",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("opted_in_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("granted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("user_run_optins")
    op.drop_index("idx_assets_team", table_name="assets")
    op.drop_index("idx_assets_type", table_name="assets")
    op.drop_table("assets")
