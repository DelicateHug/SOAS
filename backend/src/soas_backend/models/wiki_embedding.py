"""Wiki embedding storage for local RAG."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class WikiEmbedding(Base):
    __tablename__ = "wiki_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA-256 of chunk_text — lets the indexer skip chunks that haven't changed across re-indexes.
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Stored as JSON array of floats. Cosine similarity computed in Python (numpy).
    embedding: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    page_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    page = relationship("WikiPage")

    __table_args__ = (
        UniqueConstraint("page_id", "chunk_index", name="uq_wiki_embeddings_page_chunk"),
        Index("idx_wiki_embeddings_page", "page_id"),
        Index("idx_wiki_embeddings_model", "model_name"),
    )


class WikiEmbeddingStatus(Base):
    __tablename__ = "wiki_embedding_status"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE"), primary_key=True
    )
    indexed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="'pending'", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    page = relationship("WikiPage")
