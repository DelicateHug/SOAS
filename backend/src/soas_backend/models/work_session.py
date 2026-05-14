"""WorkSession — analyst time-tracking against an incident or case.

A session is created when the user clicks "Start work". Only ONE session
per user can be `active` at a time; starting a second auto-pauses any
previously-running one.

  state machine: active <-> paused -> closed (terminal)

Used by:
  - Sidebar work widget (live timer)
  - Incident/case timeline (entries emitted on every transition)
  - SLA computation (started_at bounds MTTI)
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Exactly one of incident_id / case_id must be set (CHECK enforced at DB).
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )
    # active / paused / closed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Total accumulated time across all "active" segments; updated on each
    # pause and on close so the UI never needs to walk segment history.
    accumulated_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # When the most recent "active" segment began. NULL while paused.
    active_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", foreign_keys=[user_id])
    incident = relationship("Incident", foreign_keys=[incident_id])
    case = relationship("Case", foreign_keys=[case_id])

    __table_args__ = (
        CheckConstraint(
            "(incident_id IS NOT NULL AND case_id IS NULL) OR "
            "(incident_id IS NULL AND case_id IS NOT NULL)",
            name="ck_work_session_target_xor",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'closed')",
            name="ck_work_session_status",
        ),
        Index("idx_work_sessions_user_status", "user_id", "status"),
        Index("idx_work_sessions_incident", "incident_id"),
        Index("idx_work_sessions_case", "case_id"),
    )
