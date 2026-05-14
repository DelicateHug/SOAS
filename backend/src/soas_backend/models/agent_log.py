"""AgentLog — centralized structured logs keyed by agenttype_id.

Any SOAS service can post log events here via /agents/{id}/logs.
Retention is short by default; an admin task can prune older rows.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agenttype_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Conventional levels: debug / info / warn / error / fatal
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    # Free-text message, capped client-side to ~16KB
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional structured payload (request id, exception class, etc.)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Optional: agent-reported version at log time, useful for diffing
    # behavior between releases.
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # When the event happened on the agent (may differ from created_at if batched).
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_agent_logs_agent_created", "agenttype_id", "created_at"),
        Index("idx_agent_logs_level_created", "level", "created_at"),
    )
