"""SLA definitions + daily snapshots.

A definition declares: key, target_seconds, the dimension we group
compliance by (e.g. severity, team, category_key), and which start/end
column on incidents bounds the SLA window.

Snapshots are written daily by a Celery task; each row records the
compliance percentage for one (sla_key, dim_value, day) tuple.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class SLADefinition(Base):
    __tablename__ = "sla_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Which incident columns define the duration window. start defaults to
    # created_at; end is one of {detected_at, resolved_at, closed_at}.
    start_column: Mapped[str] = mapped_column(String(32), nullable=False, default="created_at")
    end_column: Mapped[str] = mapped_column(String(32), nullable=False, default="resolved_at")
    target_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # Dimension to bucket compliance by ("severity", "category_key", "team_id", "(global)").
    dimension: Mapped[str] = mapped_column(String(32), nullable=False, default="(global)")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SLASnapshot(Base):
    __tablename__ = "sla_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sla_key: Mapped[str] = mapped_column(String(64), nullable=False)
    dim_value: Mapped[str] = mapped_column(String(200), nullable=False, default="(global)")
    captured_for: Mapped[date] = mapped_column(Date, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compliant_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compliance_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p50_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("sla_key", "dim_value", "captured_for", name="uq_sla_snapshot_day"),
        Index("idx_sla_snapshots_key_day", "sla_key", "captured_for"),
    )
