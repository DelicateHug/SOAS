"""Append rows to job_ticks; best-effort."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.job_tick import JobTick

logger = logging.getLogger(__name__)


class JobTickService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        job_id: UUID,
        decision: str,
        reason: str | None = None,
        execution_id: UUID | None = None,
        actor_id: UUID | None = None,
        extra: dict[str, Any] | None = None,
    ) -> JobTick | None:
        try:
            row = JobTick(
                job_id=job_id,
                decision=decision,
                reason=reason,
                execution_id=execution_id,
                actor_id=actor_id,
                extra=extra or {},
            )
            self.db.add(row)
            await self.db.flush()
            return row
        except Exception:
            logger.exception("job_tick.record failed job=%s decision=%s", job_id, decision)
            return None

    async def recent(self, job_id: UUID, limit: int = 100) -> list[JobTick]:
        q = (
            select(JobTick)
            .where(JobTick.job_id == job_id)
            .order_by(JobTick.created_at.desc())
            .limit(min(limit, 500))
        )
        rs = await self.db.execute(q)
        return list(rs.scalars().all())
