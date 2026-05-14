"""Chat mentions and read receipts.

A chat mention is an @-reference in a case/incident note that targets a
specific user. The mention generates a `mentioned` row for that user;
clearing it marks the mention as read.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class ChatMention(Base):
    __tablename__ = "chat_mentions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The target user being mentioned
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The user who wrote the mention
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # XOR target: one of these is set
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )
    # The kind of source the mention came from: incident_note / case_note / chat_message
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Free-text excerpt for the notification UI
    excerpt: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_chat_mentions_user_unread", "user_id", "is_read"),
        Index("idx_chat_mentions_incident", "incident_id"),
        Index("idx_chat_mentions_case", "case_id"),
    )


class ChatReadReceipt(Base):
    """Marks the last-seen position of a user inside a chat thread.

    Used so 'unread mention count' badges and 'jump to last unread'
    behavior work consistently across browser tabs.
    """
    __tablename__ = "chat_read_receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    thread_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    last_read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "thread_kind", "thread_id", name="uq_chat_read_receipt"),
        Index("idx_chat_read_receipts_user", "user_id"),
    )
