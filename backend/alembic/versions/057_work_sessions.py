"""Phase 11.3: work_sessions — analyst time tracking.

Revision ID: 057
Revises: 056
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("accumulated_seconds", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("active_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(incident_id IS NOT NULL AND case_id IS NULL) OR "
            "(incident_id IS NULL AND case_id IS NOT NULL)",
            name="ck_work_session_target_xor",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'closed')",
            name="ck_work_session_status",
        ),
    )
    op.create_index("idx_work_sessions_user_status", "work_sessions", ["user_id", "status"])
    op.create_index("idx_work_sessions_incident", "work_sessions", ["incident_id"])
    op.create_index("idx_work_sessions_case", "work_sessions", ["case_id"])


def downgrade() -> None:
    op.drop_index("idx_work_sessions_case", table_name="work_sessions")
    op.drop_index("idx_work_sessions_incident", table_name="work_sessions")
    op.drop_index("idx_work_sessions_user_status", table_name="work_sessions")
    op.drop_table("work_sessions")
