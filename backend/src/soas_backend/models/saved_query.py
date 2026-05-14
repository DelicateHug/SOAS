"""SavedQuery — reusable query library for hunting / reporting.

Query types reflect SOAS's connector model:
  - "incidents_sql"  → safe DSL evaluated by the widget engine's SQL layer
  - "leql"           → run against a configured connector
  - "kql"            → run against a configured connector
  - "raw_sql"        → admin-only, read-only, SELECT-only

Templating with ${case_id}, ${hostname} etc. is substituted at execution
time by the saved_query_service.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class SavedQuery(Base):
    __tablename__ = "saved_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_type: Mapped[str] = mapped_column(String(32), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    connector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_sources.id", ondelete="SET NULL"), nullable=True
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    favorite_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner = relationship("User", foreign_keys=[owner_id])
    favorites: Mapped[list["SavedQueryFavorite"]] = relationship(
        back_populates="saved_query", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_saved_queries_owner", "owner_id"),
        Index("idx_saved_queries_type", "query_type"),
    )


class SavedQueryFavorite(Base):
    __tablename__ = "saved_query_favorites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    saved_query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saved_queries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    saved_query: Mapped["SavedQuery"] = relationship(back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("saved_query_id", "user_id", name="uq_saved_query_favorite"),
        Index("idx_saved_query_favorites_user", "user_id"),
    )
