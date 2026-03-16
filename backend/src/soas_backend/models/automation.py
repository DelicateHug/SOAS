"""Automation models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from soas_backend.database import Base


class Automation(Base):
    __tablename__ = "automations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    graph_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    graph_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    script_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    script_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parameters: Mapped[list] = mapped_column(JSONB, default=list)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    trigger_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    is_trigger_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Documentation (markdown/HTML)
    documentation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Collaboration lock
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, default=None
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Team scoping
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )

    creator = relationship("User", foreign_keys=[created_by])
    team = relationship("Team", foreign_keys=[team_id])
    permissions: Mapped[list["AutomationPermission"]] = relationship(
        back_populates="automation", cascade="all, delete-orphan"
    )
    dependencies: Mapped[list["AutomationDependency"]] = relationship(
        back_populates="automation", cascade="all, delete-orphan"
    )
    versions: Mapped[list["AutomationVersion"]] = relationship(
        back_populates="automation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_automations_team_id", "team_id"),
    )


class AutomationPermission(Base):
    __tablename__ = "automation_permissions"

    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automations.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_execute: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_add: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    automation: Mapped["Automation"] = relationship(back_populates="permissions")
    role = relationship("Role")


class AutomationDependency(Base):
    __tablename__ = "automation_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automations.id", ondelete="CASCADE"), nullable=False
    )
    dependency_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'automation' or 'code_block'
    dependency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    automation: Mapped["Automation"] = relationship(back_populates="dependencies")

    __table_args__ = (
        UniqueConstraint("automation_id", "dependency_type", "dependency_id", name="uq_auto_deps_unique"),
        Index("idx_auto_deps_automation", "automation_id"),
        Index("idx_auto_deps_dependency", "dependency_type", "dependency_id"),
    )


class AutomationVersion(Base):
    __tablename__ = "automation_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    automation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automations.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    graph_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    trigger_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    is_trigger_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    documentation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    automation: Mapped["Automation"] = relationship(back_populates="versions")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("automation_id", "version_number", name="uq_auto_version_number"),
    )
