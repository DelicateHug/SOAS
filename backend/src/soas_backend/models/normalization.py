"""Normalization models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class NormalizationGroup(Base):
    __tablename__ = "normalization_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    rules: Mapped[list["NormalizationRule"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class NormalizationRule(Base):
    __tablename__ = "normalization_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("normalization_groups.id"), nullable=False
    )
    source_path: Mapped[str] = mapped_column(String(500), nullable=False)
    target_field: Mapped[str] = mapped_column(String(200), nullable=False)
    transform_type: Mapped[str] = mapped_column(String(20), nullable=False, default="direct")
    transform_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    group: Mapped["NormalizationGroup"] = relationship(back_populates="rules")

    __table_args__ = (
        Index("idx_normalization_rules_enabled", "is_enabled"),
    )
