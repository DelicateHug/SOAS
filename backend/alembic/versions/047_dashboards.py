"""Phase 2: dashboards + dashboard_widgets.

Revision ID: 047
Revises: 046
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("layout", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_dashboards_owner", "dashboards", ["owner_id"])
    op.create_index("idx_dashboards_team", "dashboards", ["team_id"])
    op.create_index("idx_dashboards_public", "dashboards", ["is_public"])

    op.create_table(
        "dashboard_widgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dashboard_id", UUID(as_uuid=True), sa.ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("widget_type", sa.String(32), nullable=False),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("width", sa.Integer, nullable=False, server_default=sa.text("6")),
        sa.Column("height", sa.Integer, nullable=False, server_default=sa.text("2")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_dashboard_widgets_dashboard", "dashboard_widgets", ["dashboard_id"])


def downgrade() -> None:
    op.drop_index("idx_dashboard_widgets_dashboard", table_name="dashboard_widgets")
    op.drop_table("dashboard_widgets")
    op.drop_index("idx_dashboards_public", table_name="dashboards")
    op.drop_index("idx_dashboards_team", table_name="dashboards")
    op.drop_index("idx_dashboards_owner", table_name="dashboards")
    op.drop_table("dashboards")
