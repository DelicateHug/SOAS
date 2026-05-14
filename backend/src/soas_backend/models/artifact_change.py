"""ArtifactChange — audit row for every CUD operation across all artifact types.

Powers the change-tracking dashboard widgets (Tier C). One row per
create/update/delete/fork/rename/restore/snapshot. Append-only.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class ArtifactChange(Base):
    __tablename__ = "artifact_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # The artifact kind, e.g. "automation", "wiki_page", "case", "incident",
    # "code_block", "saved_query", "dashboard", "widget", "alert_category", "sla_definition".
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    # The mutation, e.g. "create", "update", "delete", "fork", "rename",
    # "restore", "snapshot", "publish", "lock", "unlock".
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    target_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_artifact_changes_kind_created", "kind", "created_at"),
        Index("idx_artifact_changes_actor", "actor_id"),
        Index("idx_artifact_changes_target", "target_id"),
        Index("idx_artifact_changes_created", "created_at"),
    )
