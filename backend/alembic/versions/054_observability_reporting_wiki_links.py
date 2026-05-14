"""Phase 10: observability + reporting + wiki backlinks.

Revision ID: 054
Revises: 053
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instance_metric_samples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", sa.String(200), nullable=False),
        sa.Column("role", sa.String(32), nullable=True),
        sa.Column("cpu_pct", sa.Float, nullable=True),
        sa.Column("mem_pct", sa.Float, nullable=True),
        sa.Column("mem_rss_bytes", sa.BigInteger, nullable=True),
        sa.Column("net_in_bytes", sa.BigInteger, nullable=True),
        sa.Column("net_out_bytes", sa.BigInteger, nullable=True),
        sa.Column("uptime_seconds", sa.Integer, nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_instance_metric_samples_instance_captured", "instance_metric_samples", ["instance_id", "captured_at"])

    op.create_table(
        "network_io_minutely",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("minute_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("bytes_in", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("bytes_out", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("request_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    op.create_index("idx_network_io_minutely_minute_source", "network_io_minutely", ["minute_utc", "source"], unique=True)

    op.create_table(
        "page_load_samples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("server_duration_ms", sa.Integer, nullable=True),
        sa.Column("ttfb_ms", sa.Integer, nullable=True),
        sa.Column("dom_ready_ms", sa.Integer, nullable=True),
        sa.Column("load_ms", sa.Integer, nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_page_load_samples_path_created", "page_load_samples", ["path", "created_at"])

    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sections", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_template", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_reports_case", "reports", ["case_id"])
    op.create_index("idx_reports_owner", "reports", ["owner_id"])

    op.create_table(
        "wiki_page_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_page_id", UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_page_id", UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_slug", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_page_id", "target_slug", name="uq_wiki_page_link"),
    )
    op.create_index("idx_wiki_page_links_target", "wiki_page_links", ["target_page_id"])
    op.create_index("idx_wiki_page_links_target_slug", "wiki_page_links", ["target_slug"])


def downgrade() -> None:
    op.drop_index("idx_wiki_page_links_target_slug", table_name="wiki_page_links")
    op.drop_index("idx_wiki_page_links_target", table_name="wiki_page_links")
    op.drop_table("wiki_page_links")
    op.drop_index("idx_reports_owner", table_name="reports")
    op.drop_index("idx_reports_case", table_name="reports")
    op.drop_table("reports")
    op.drop_index("idx_page_load_samples_path_created", table_name="page_load_samples")
    op.drop_table("page_load_samples")
    op.drop_index("idx_network_io_minutely_minute_source", table_name="network_io_minutely")
    op.drop_table("network_io_minutely")
    op.drop_index("idx_instance_metric_samples_instance_captured", table_name="instance_metric_samples")
    op.drop_table("instance_metric_samples")
