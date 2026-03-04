"""Automation trigger log model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, TEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class AutomationTriggerLog(Base):
    __tablename__ = "automation_trigger_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automations.id"), nullable=False
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False
    )
    execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("execution_logs.id"), nullable=True
    )
    matched_tags: Mapped[list[str]] = mapped_column(ARRAY(TEXT()), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="triggered")

    automation = relationship("Automation")
    incident = relationship("Incident")
    execution = relationship("ExecutionLog")

    __table_args__ = (
        Index("idx_trigger_log_automation", "automation_id"),
        Index("idx_trigger_log_incident", "incident_id"),
    )
