"""Phase 4: saved_queries + saved_query_favorites.

Revision ID: 049
Revises: 048
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_queries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("query_type", sa.String(32), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("connector_id", UUID(as_uuid=True), sa.ForeignKey("webhook_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("favorite_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_saved_queries_owner", "saved_queries", ["owner_id"])
    op.create_index("idx_saved_queries_type", "saved_queries", ["query_type"])

    op.create_table(
        "saved_query_favorites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("saved_query_id", UUID(as_uuid=True), sa.ForeignKey("saved_queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("saved_query_id", "user_id", name="uq_saved_query_favorite"),
    )
    op.create_index("idx_saved_query_favorites_user", "saved_query_favorites", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_saved_query_favorites_user", table_name="saved_query_favorites")
    op.drop_table("saved_query_favorites")
    op.drop_index("idx_saved_queries_type", table_name="saved_queries")
    op.drop_index("idx_saved_queries_owner", table_name="saved_queries")
    op.drop_table("saved_queries")
