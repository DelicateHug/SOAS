"""Git sync log model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class GitSyncLog(Base):
    __tablename__ = "git_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sync_type: Mapped[str] = mapped_column(String(20), nullable=False)  # push | pull | full | initial
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success | failed | partial
    entities_pushed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entities_pulled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conflicts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(200), nullable=False)  # scheduled | manual | UUID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
