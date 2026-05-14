"""Phase 8: case_ai_chats + ai_actions.

Revision ID: 053
Revises: 052
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_ai_chats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("transcript", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("is_favorite", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("token_total", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_case_ai_chats_case", "case_ai_chats", ["case_id"])
    op.create_index("idx_case_ai_chats_incident", "case_ai_chats", ["incident_id"])
    op.create_index("idx_case_ai_chats_owner", "case_ai_chats", ["owner_id"])

    op.create_table(
        "ai_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("page_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("allowed_mcp_tools", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("context_fields", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("result_kind", sa.String(16), nullable=False, server_default=sa.text("'markdown'")),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("100")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ai_actions_page", "ai_actions", ["page_key", "sort_order"])

    # Seed a couple of default actions matching case-managment.
    op.execute("""
        INSERT INTO ai_actions (page_key, label, icon, description, system_prompt, context_fields, sort_order)
        VALUES
          ('case', 'Summarize this case', 'sparkles',
           'AI-generated summary of the case context, incidents, and notes',
           'You are a SOC analyst. Read the case context and write a 5-bullet summary including: 1) initial trigger, 2) affected assets, 3) timeline, 4) findings, 5) next steps. Context: {case_id}',
           ARRAY['case_id'], 10),
          ('incident', 'Suggest next steps', 'lightbulb',
           'Recommend investigation steps given the alert',
           'You are a SOC analyst triaging an incident. Given the incident metadata, recommend the top 5 investigation steps. Incident: {incident_id}',
           ARRAY['incident_id'], 10),
          ('wiki', 'Improve this page', 'wand',
           'Rewrites the page for clarity while preserving meaning',
           'Improve clarity and structure of the wiki page below. Preserve all factual claims and markdown formatting. Page slug: {page_slug}',
           ARRAY['page_slug'], 10)
    """)


def downgrade() -> None:
    op.drop_index("idx_ai_actions_page", table_name="ai_actions")
    op.drop_table("ai_actions")
    op.drop_index("idx_case_ai_chats_owner", table_name="case_ai_chats")
    op.drop_index("idx_case_ai_chats_incident", table_name="case_ai_chats")
    op.drop_index("idx_case_ai_chats_case", table_name="case_ai_chats")
    op.drop_table("case_ai_chats")
