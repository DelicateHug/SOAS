"""Phase 11.4: evidence snapshots, chat mentions/read receipts, security events.

Revision ID: 058
Revises: 057
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("source_ref", sa.String(200), nullable=True),
        sa.Column("query_text", sa.Text, nullable=True),
        sa.Column("query_hash", sa.String(64), nullable=True),
        sa.Column("columns", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rows", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("row_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_evidence_snapshots_incident", "evidence_snapshots", ["incident_id"])
    op.create_index("idx_evidence_snapshots_case", "evidence_snapshots", ["case_id"])
    op.create_index("idx_evidence_snapshots_hash", "evidence_snapshots", ["query_hash"])

    op.create_table(
        "chat_mentions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref", UUID(as_uuid=True), nullable=True),
        sa.Column("excerpt", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_chat_mentions_user_unread", "chat_mentions", ["user_id", "is_read"])
    op.create_index("idx_chat_mentions_incident", "chat_mentions", ["incident_id"])
    op.create_index("idx_chat_mentions_case", "chat_mentions", ["case_id"])

    op.create_table(
        "chat_read_receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_kind", sa.String(32), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "thread_kind", "thread_id", name="uq_chat_read_receipt"),
    )
    op.create_index("idx_chat_read_receipts_user", "chat_read_receipts", ["user_id"])

    op.create_table(
        "security_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default=sa.text("'info'")),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_label", sa.String(200), nullable=True),
        sa.Column("target_kind", sa.String(64), nullable=True),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_label", sa.String(500), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("extra", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_security_events_type_created", "security_events", ["event_type", "created_at"])
    op.create_index("idx_security_events_actor", "security_events", ["actor_id"])
    op.create_index("idx_security_events_severity", "security_events", ["severity"])
    op.create_index("idx_security_events_created", "security_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_security_events_created", table_name="security_events")
    op.drop_index("idx_security_events_severity", table_name="security_events")
    op.drop_index("idx_security_events_actor", table_name="security_events")
    op.drop_index("idx_security_events_type_created", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("idx_chat_read_receipts_user", table_name="chat_read_receipts")
    op.drop_table("chat_read_receipts")
    op.drop_index("idx_chat_mentions_case", table_name="chat_mentions")
    op.drop_index("idx_chat_mentions_incident", table_name="chat_mentions")
    op.drop_index("idx_chat_mentions_user_unread", table_name="chat_mentions")
    op.drop_table("chat_mentions")
    op.drop_index("idx_evidence_snapshots_hash", table_name="evidence_snapshots")
    op.drop_index("idx_evidence_snapshots_case", table_name="evidence_snapshots")
    op.drop_index("idx_evidence_snapshots_incident", table_name="evidence_snapshots")
    op.drop_table("evidence_snapshots")
