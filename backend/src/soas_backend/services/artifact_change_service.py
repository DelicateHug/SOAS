"""ArtifactChange recorder.

Service modules call `record(...)` from inside their CUD flows.
Best-effort writes: a DB error here MUST NOT block the underlying
operation, so callers should wrap in try/except (or let SQLAlchemy
flush at request end fail soft via the session-level handling).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.artifact_change import ArtifactChange

logger = logging.getLogger(__name__)


class ArtifactChangeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        kind: str,
        action: str,
        target_id: UUID | None = None,
        target_label: str | None = None,
        actor_id: UUID | None = None,
        summary: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ArtifactChange | None:
        """Append one audit row. Returns the row, or None if the write failed.

        Never raises — change-tracking is observability, not a correctness
        guarantee.
        """
        try:
            row = ArtifactChange(
                kind=kind,
                action=action,
                target_id=target_id,
                target_label=(target_label[:500] if target_label else None),
                actor_id=actor_id,
                summary=summary,
                extra=extra or {},
            )
            self.db.add(row)
            await self.db.flush()
            return row
        except Exception:
            logger.exception("artifact_change.record failed kind=%s action=%s", kind, action)
            return None

    async def list_recent(
        self,
        *,
        limit: int = 100,
        kind: str | None = None,
        action: str | None = None,
        actor_id: UUID | None = None,
    ) -> list[ArtifactChange]:
        q = select(ArtifactChange).order_by(ArtifactChange.created_at.desc())
        if kind:
            q = q.where(ArtifactChange.kind == kind)
        if action:
            q = q.where(ArtifactChange.action == action)
        if actor_id:
            q = q.where(ArtifactChange.actor_id == actor_id)
        q = q.limit(min(limit, 1000))
        result = await self.db.execute(q)
        return list(result.scalars().all())
