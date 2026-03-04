"""Webhook models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="custom")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_severity: Mapped[str] = mapped_column(String(20), default="medium")
    default_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_sources.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_received: Mapped[int] = mapped_column(Integer, default=0)

    creator = relationship("User", foreign_keys=[created_by])
    source = relationship("WebhookSource", back_populates="webhooks")
    logs: Mapped[list["WebhookLog"]] = relationship(
        back_populates="webhook", cascade="all, delete-orphan"
    )
    __table_args__ = (
        Index("idx_webhooks_secret_token", "secret_token"),
        Index("idx_webhooks_enabled", "is_enabled"),
    )


class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    request_body: Mapped[dict] = mapped_column(JSONB, default=dict)
    normalized_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    webhook: Mapped["Webhook"] = relationship(back_populates="logs")
    incident = relationship("Incident")

    __table_args__ = (
        Index("idx_webhook_logs_webhook_created", "webhook_id", created_at.desc()),
    )
