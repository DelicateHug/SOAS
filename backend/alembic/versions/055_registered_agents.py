"""Phase 11: registered_agents roster + agenttype_id on instance_metric_samples.

Revision ID: 055
Revises: 054
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registered_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agenttype_id", sa.String(64), nullable=False, unique=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("fresh_seconds", sa.Integer, nullable=False, server_default=sa.text("60")),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_registered_agents_role", "registered_agents", ["role"])

    op.add_column(
        "instance_metric_samples",
        sa.Column("agenttype_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "idx_instance_metric_samples_agent_captured",
        "instance_metric_samples",
        ["agenttype_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_instance_metric_samples_agent_captured", table_name="instance_metric_samples")
    op.drop_column("instance_metric_samples", "agenttype_id")
    op.drop_index("idx_registered_agents_role", table_name="registered_agents")
    op.drop_table("registered_agents")
