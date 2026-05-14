"""Dashboard + DashboardWidget models.

A dashboard is an owner-scoped, optionally public collection of widget
configs. The widget config is a JSON document interpreted by the
widget_engine; the engine whitelist-validates every field reference
before composing SQL.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class Dashboard(Base):
    __tablename__ = "dashboards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    layout: Mapped[dict] = mapped_column(JSONB, default=dict)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner = relationship("User", foreign_keys=[owner_id])
    team = relationship("Team", foreign_keys=[team_id])
    widgets: Mapped[list["DashboardWidget"]] = relationship(
        back_populates="dashboard", cascade="all, delete-orphan", order_by="DashboardWidget.position"
    )

    __table_args__ = (
        Index("idx_dashboards_owner", "owner_id"),
        Index("idx_dashboards_team", "team_id"),
        Index("idx_dashboards_public", "is_public"),
    )


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Widget type: top_n, timeseries, counter, pie, stacked_bar, table, sql,
    # duration_stat, ratio, sla_table, sla_compliance, app_wide_sla, sla_trend,
    # tokens_counter, tokens_top_n, tokens_timeseries, tokens_pie, tokens_table,
    # changes_counter, changes_top_n, changes_timeseries, changes_pie, changes_table.
    widget_type: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=6)  # 12-col grid
    height: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    dashboard = relationship("Dashboard", back_populates="widgets")

    __table_args__ = (
        Index("idx_dashboard_widgets_dashboard", "dashboard_id"),
    )
