"""Execution log queries and management."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.automation import Automation
from soas_backend.models.execution import ExecutionLog


class ExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, execution_id: UUID) -> ExecutionLog | None:
        result = await self.db.execute(
            select(ExecutionLog)
            .options(
                selectinload(ExecutionLog.user),
                selectinload(ExecutionLog.automation),
            )
            .where(ExecutionLog.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list_executions(
        self,
        automation_id: UUID | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[ExecutionLog], int]:
        # Build filter conditions once, reuse for count and data queries
        conditions = []
        if automation_id:
            conditions.append(ExecutionLog.automation_id == automation_id)
        if status:
            conditions.append(ExecutionLog.status == status)
        if started_after:
            conditions.append(ExecutionLog.started_at >= started_after)
        if started_before:
            conditions.append(ExecutionLog.started_at <= started_before)

        count_query = select(func.count(ExecutionLog.id))
        for cond in conditions:
            count_query = count_query.where(cond)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(ExecutionLog)
            .options(
                selectinload(ExecutionLog.user),
                selectinload(ExecutionLog.automation),
            )
            .order_by(ExecutionLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for cond in conditions:
            query = query.where(cond)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def cancel(self, execution_id: UUID) -> bool:
        execution = await self.get(execution_id)
        if not execution:
            return False
        if execution.status not in ("pending", "queued", "running"):
            return False

        execution.status = "cancelled"
        await self.db.flush()

        # Revoke Celery task if possible
        if execution.celery_task_id:
            from soas_backend.celery_proxy import get_celery

            celery = get_celery()
            celery.control.revoke(execution.celery_task_id, terminate=True)

        return True

    async def get_stats(self) -> dict:
        """Get execution statistics for dashboard."""
        result = await self.db.execute(
            select(
                func.count(ExecutionLog.id).label("total"),
                func.count(
                    case(
                        (
                            ExecutionLog.status.in_(
                                ["pending", "queued", "running"]
                            ),
                            ExecutionLog.id,
                        ),
                    )
                ).label("running"),
                func.count(
                    case(
                        (ExecutionLog.status == "completed", ExecutionLog.id),
                    )
                ).label("completed"),
                func.count(
                    case(
                        (
                            ExecutionLog.status.in_(["failed", "timed_out"]),
                            ExecutionLog.id,
                        ),
                    )
                ).label("failed"),
                func.avg(
                    case(
                        (
                            ExecutionLog.duration_ms.isnot(None),
                            ExecutionLog.duration_ms,
                        ),
                    )
                ).label("avg_duration"),
            )
        )
        row = result.one()

        return {
            "total": row.total or 0,
            "running": row.running or 0,
            "completed": row.completed or 0,
            "failed": row.failed or 0,
            "avg_duration_ms": int(row.avg_duration) if row.avg_duration else 0,
        }
