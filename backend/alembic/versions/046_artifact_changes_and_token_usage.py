"""Phase 1 foundation: artifact_changes + token_usage.

Append-only audit of every CUD across all artifact types, plus
LLM-token accounting for AI features and dashboard widgets.

Revision ID: 046
Revises: 045
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_changes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_label", sa.String(500), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("extra", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_artifact_changes_kind_created", "artifact_changes", ["kind", "created_at"])
    op.create_index("idx_artifact_changes_actor", "artifact_changes", ["actor_id"])
    op.create_index("idx_artifact_changes_target", "artifact_changes", ["target_id"])
    op.create_index("idx_artifact_changes_created", "artifact_changes", ["created_at"])

    op.create_table(
        "token_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("caller", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("cache_create_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_kind", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_token_usage_caller_created", "token_usage", ["caller", "created_at"])
    op.create_index("idx_token_usage_user_created", "token_usage", ["user_id", "created_at"])
    op.create_index("idx_token_usage_model_created", "token_usage", ["model", "created_at"])
    op.create_index("idx_token_usage_created", "token_usage", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_token_usage_created", table_name="token_usage")
    op.drop_index("idx_token_usage_model_created", table_name="token_usage")
    op.drop_index("idx_token_usage_user_created", table_name="token_usage")
    op.drop_index("idx_token_usage_caller_created", table_name="token_usage")
    op.drop_table("token_usage")

    op.drop_index("idx_artifact_changes_created", table_name="artifact_changes")
    op.drop_index("idx_artifact_changes_target", table_name="artifact_changes")
    op.drop_index("idx_artifact_changes_actor", table_name="artifact_changes")
    op.drop_index("idx_artifact_changes_kind_created", table_name="artifact_changes")
    op.drop_table("artifact_changes")
