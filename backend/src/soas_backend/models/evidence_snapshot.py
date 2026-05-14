"""EvidenceSnapshot — frozen tabular result captured against a case/incident.

Distinct from case_files (which stores binary attachments). An evidence
snapshot is a 2D array of cells captured from a hunting query, alert
table, or AI action output, with the columns preserved and a hash of
the query text for dedup. Matches case-managment's case_evidence concept.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from soas_backend.database import Base


class EvidenceSnapshot(Base):
    __tablename__ = "evidence_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )
    # Free-text label, e.g. "Logins from suspicious IP"
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Where the snapshot came from: manual / saved_query / ai_action / playbook / hunting
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    # Optional pointer back to the originating query/automation
    source_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Free-text echo of the query that produced this snapshot
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # sha256 of (source, query_text) — used for dedup channels
    query_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Column order matters; stored as an ordered list of names.
    columns: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    # Rows are list-of-lists keyed positionally to columns.
    rows: Mapped[list[list]] = mapped_column(JSONB, default=list, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_evidence_snapshots_incident", "incident_id"),
        Index("idx_evidence_snapshots_case", "case_id"),
        Index("idx_evidence_snapshots_hash", "query_hash"),
    )
