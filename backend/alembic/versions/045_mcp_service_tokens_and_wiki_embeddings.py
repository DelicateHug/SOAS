"""Add service_tokens and wiki_embeddings tables for MCP integration and RAG.

Revision ID: 045
Revises: 044
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Long-lived bearer tokens for non-interactive clients (MCP, CI, automations).
    # Distinct from refresh_tokens, which are short-lived and tied to a user session.
    op.create_table(
        "service_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("scopes", sa.ARRAY(sa.String), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(45), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_service_tokens_token_hash", "service_tokens", ["token_hash"])
    op.create_index("idx_service_tokens_active", "service_tokens", ["is_active", "revoked_at"])

    # Wiki embeddings — chunk-level vectors for semantic retrieval.
    # Stored as JSONB float array. Cosine similarity is computed in Python via the RAG service.
    # Switching to pgvector later only requires altering the column type; the service code
    # already uses numpy for cosine, so the path is well-defined.
    op.create_table(
        "wiki_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("page_id", UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("chunk_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("embedding", JSONB, nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("model_dimension", sa.Integer, nullable=False),
        sa.Column("page_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("page_id", "chunk_index", name="uq_wiki_embeddings_page_chunk"),
    )
    op.create_index("idx_wiki_embeddings_page", "wiki_embeddings", ["page_id"])
    op.create_index("idx_wiki_embeddings_model", "wiki_embeddings", ["model_name"])

    # Index status tracking — one row per page, lets us know which pages are up-to-date.
    op.create_table(
        "wiki_embedding_status",
        sa.Column("page_id", UUID(as_uuid=True), sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("indexed_version", sa.Integer, nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_table("wiki_embedding_status")
    op.drop_index("idx_wiki_embeddings_model", table_name="wiki_embeddings")
    op.drop_index("idx_wiki_embeddings_page", table_name="wiki_embeddings")
    op.drop_table("wiki_embeddings")
    op.drop_index("idx_service_tokens_active", table_name="service_tokens")
    op.drop_index("idx_service_tokens_token_hash", table_name="service_tokens")
    op.drop_table("service_tokens")
