"""Issue models for centralized issue tracking."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Graph annotation data (for automation-targeted issues)
    # Structure: { "x": float, "y": float, "width": float, "height": float,
    #              "automation_version": int, "node_id": str | null }
    graph_annotation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    owner = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
    links: Mapped[list["IssueLink"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )
    notes: Mapped[list["IssueNote"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )
    checklist_items: Mapped[list["IssueChecklistItem"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_issues_status", "status"),
        Index("idx_issues_assigned_to", "assigned_to"),
        Index("idx_issues_created_by", "created_by"),
    )


class IssueLink(Base):
    """Polymorphic link between an issue and any target entity."""

    __tablename__ = "issue_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    issue: Mapped["Issue"] = relationship(back_populates="links")

    __table_args__ = (
        UniqueConstraint("issue_id", "target_type", "target_id", name="uq_issue_link_unique"),
        Index("idx_issue_links_issue", "issue_id"),
        Index("idx_issue_links_target", "target_type", "target_id"),
    )


class IssueNote(Base):
    """Notes on issues with evidence marking."""

    __tablename__ = "issue_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    issue = relationship("Issue", back_populates="notes")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        Index("idx_issue_notes_issue", "issue_id"),
        Index("idx_issue_notes_evidence", "issue_id", "is_evidence"),
    )


class IssueChecklistItem(Base):
    """Checklist items on issues with per-item ownership."""

    __tablename__ = "issue_checklist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    issue = relationship("Issue", back_populates="checklist_items")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_issue_checklist_issue", "issue_id"),
    )
