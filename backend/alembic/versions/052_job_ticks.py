"""Phase 7: job_ticks audit trail for scheduler decisions.

Revision ID: 052
Revises: 051
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_ticks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("execution_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extra", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_job_ticks_job_created", "job_ticks", ["job_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_job_ticks_job_created", table_name="job_ticks")
    op.drop_table("job_ticks")
