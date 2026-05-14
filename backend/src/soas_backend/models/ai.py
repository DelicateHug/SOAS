"""AI features models — case chat threads + AI Actions.

A CaseAIChat is a named, persistent conversation owned by one user
inside one case (or incident). The transcript is JSONB
[{role, content, ts}], capped at 4MB.

AIAction is a registry row that lights up an inline "AI Action" button
on a page (e.g. "Summarize this case"). The system_prompt is run
through the CLI/API runner; allowed_mcp_tools narrows what tools the
agent may invoke.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class CaseAIChat(Base):
    __tablename__ = "case_ai_chats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    transcript: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_case_ai_chats_case", "case_id"),
        Index("idx_case_ai_chats_incident", "incident_id"),
        Index("idx_case_ai_chats_owner", "owner_id"),
    )


class AIAction(Base):
    __tablename__ = "ai_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The page surface this action shows on: cases, incidents, wiki, dashboards, queries
    page_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    # Tools the agent is allowed to invoke (MCP tool names). Empty = none.
    allowed_mcp_tools: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # Field names from the page context to interpolate into the prompt
    # via {field_name} placeholders.
    context_fields: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    result_kind: Mapped[str] = mapped_column(String(16), default="markdown", nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_ai_actions_page", "page_key", "sort_order"),
    )
