"""Incident models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="detected")
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    raw_event: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Team scoping
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    lead = relationship("User", foreign_keys=[lead_id])
    team = relationship("Team", foreign_keys=[team_id])
    creator = relationship("User", foreign_keys=[created_by])
    assignments: Mapped[list["IncidentAssignment"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    timeline_entries = relationship(
        "TimelineEntry", back_populates="incident", cascade="all, delete-orphan"
    )
    notes: Mapped[list["IncidentNote"]] = relationship(  # noqa: F821
        back_populates="incident", cascade="all, delete-orphan"
    )
    files: Mapped[list["IncidentFile"]] = relationship(  # noqa: F821
        back_populates="incident", cascade="all, delete-orphan"
    )
    form_submissions: Mapped[list["FormSubmission"]] = relationship(  # noqa: F821
        back_populates="incident", cascade="all, delete-orphan"
    )
    case_incidents: Mapped[list["CaseIncident"]] = relationship(  # noqa: F821
        viewonly=True
    )

    __table_args__ = (
        Index("idx_incidents_severity", "severity"),
        Index("idx_incidents_status", "status"),
        Index("idx_incidents_created", created_at.desc()),
        Index("idx_incidents_team_id", "team_id"),
    )


class IncidentAssignment(Base):
    __tablename__ = "incident_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role_in_incident: Mapped[str] = mapped_column(String(100), default="responder", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    incident: Mapped["Incident"] = relationship(back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    assigner = relationship("User", foreign_keys=[assigned_by])

    __table_args__ = (UniqueConstraint("incident_id", "user_id"),)
