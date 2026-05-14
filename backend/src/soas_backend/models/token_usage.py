"""TokenUsage — Anthropic LLM token accounting.

Both `ai_subprocess` (Claude CLI shell-out, user-driven) and `ai_api`
(Anthropic SDK, worker-driven) write rows here. Powers token_* dashboard
widgets and admin token usage page.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # "cli" (user-driven via subprocess) or "api" (worker-driven via SDK)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    # The caller feature, e.g. "case_chat", "ai_action", "query_builder",
    # "widget_builder", "automation_agent_node".
    caller: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_create_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    target_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_token_usage_caller_created", "caller", "created_at"),
        Index("idx_token_usage_user_created", "user_id", "created_at"),
        Index("idx_token_usage_model_created", "model", "created_at"),
        Index("idx_token_usage_created", "created_at"),
    )
