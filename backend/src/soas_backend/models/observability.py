"""Phase 10 models: cluster instance metrics + network I/O + page load tracking."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class InstanceMetricSample(Base):
    """Per-instance CPU/mem/IO/net sample, written by the worker heartbeat."""
    __tablename__ = "instance_metric_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # Phase 11: stable agenttype_id (e.g. worker_001). Falls back to instance_id
    # when an old agent hasn't been given a stable id yet.
    agenttype_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cpu_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_rss_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_in_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_out_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_instance_metric_samples_instance_captured", "instance_id", "captured_at"),
        Index("idx_instance_metric_samples_agent_captured", "agenttype_id", "captured_at"),
    )


class NetworkIOMinutely(Base):
    """Per-minute, per-source HTTP I/O totals."""
    __tablename__ = "network_io_minutely"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    minute_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes_in: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_out: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_network_io_minutely_minute_source", "minute_utc", "source", unique=True),
    )


class PageLoadSample(Base):
    """Server- and client-side page-load timings, joined by nonce."""
    __tablename__ = "page_load_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    server_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttfb_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dom_ready_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    load_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_page_load_samples_path_created", "path", "created_at"),
    )
