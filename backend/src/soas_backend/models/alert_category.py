"""AlertCategory + AlertCategoryRule + IncidentTemplate.

Categorisation buckets that incoming incidents fall into based on
admin-configured regex rules. Drives default response policies and the
classifier_service consumed by the pre-processing pipeline.

IncidentTemplate is colocated here because it shares the admin surface
and stays simple.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class AlertCategory(Base):
    __tablename__ = "alert_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_automation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automations.id", ondelete="SET NULL"), nullable=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    rules: Mapped[list["AlertCategoryRule"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="AlertCategoryRule.sort_order"
    )


class AlertCategoryRule(Base):
    __tablename__ = "alert_category_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_categories.id", ondelete="CASCADE"), nullable=False
    )
    # The dotted JSON path inside Incident.metadata_ or Incident.raw_event we're matching.
    # Special values: "title", "summary", "source", "tags" map to the column directly.
    field: Mapped[str] = mapped_column(String(200), nullable=False)
    # Python re-compatible regex. Validated at write time.
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    case_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped["AlertCategory"] = relationship(back_populates="rules")

    __table_args__ = (
        Index("idx_alert_category_rules_category", "category_id"),
    )


class IncidentTemplate(Base):
    __tablename__ = "incident_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The defaults to apply when an analyst creates an incident from this template
    # (or when classifier matches a category that points at it).
    defaults: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
