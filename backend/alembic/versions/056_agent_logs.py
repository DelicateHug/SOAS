"""Phase 11.1: agent_logs table.

Revision ID: 056
Revises: 055
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agenttype_id", sa.String(64), nullable=False),
        sa.Column("level", sa.String(16), nullable=False, server_default=sa.text("'info'")),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("context", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_agent_logs_agent_created", "agent_logs", ["agenttype_id", "created_at"])
    op.create_index("idx_agent_logs_level_created", "agent_logs", ["level", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_agent_logs_level_created", table_name="agent_logs")
    op.drop_index("idx_agent_logs_agent_created", table_name="agent_logs")
    op.drop_table("agent_logs")
