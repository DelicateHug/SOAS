"""Form submission model -- a filled-in form attached to an incident."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    form_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", back_populates="form_submissions")
    form_definition = relationship("FormDefinition", back_populates="submissions")
    submitter = relationship("User", foreign_keys=[submitted_by])

    __table_args__ = (
        Index("idx_form_submissions_incident", "incident_id"),
        Index("idx_form_submissions_form", "form_definition_id"),
        Index("idx_form_submissions_evidence", "incident_id", "is_evidence"),
    )
