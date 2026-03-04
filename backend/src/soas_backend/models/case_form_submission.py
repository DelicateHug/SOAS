"""Case form submission model -- a filled-in form attached to a case."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class CaseFormSubmission(Base):
    __tablename__ = "case_form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
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

    case = relationship("Case", back_populates="form_submissions")
    form_definition = relationship("FormDefinition")
    submitter = relationship("User", foreign_keys=[submitted_by])

    __table_args__ = (
        Index("idx_case_form_submissions_case", "case_id"),
        Index("idx_case_form_submissions_form", "form_definition_id"),
        Index("idx_case_form_submissions_evidence", "case_id", "is_evidence"),
    )
