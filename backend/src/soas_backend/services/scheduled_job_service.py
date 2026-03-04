"""Scheduled job business logic - CRUD, schedule validation, next-run computation."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from croniter import croniter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.scheduled_job import ScheduledJob


class ScheduledJobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        automation_id: UUID,
        name: str,
        schedule_type: str,
        created_by: UUID,
        description: str | None = None,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        calendar_config: dict | None = None,
        timezone_str: str = "UTC",
        parameters: dict[str, Any] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ScheduledJob:
        # Validate the schedule configuration
        effective_cron = self._resolve_cron_expression(
            schedule_type, cron_expression, interval_seconds, calendar_config
        )

        job = ScheduledJob(
            automation_id=automation_id,
            name=name,
            description=description,
            schedule_type=schedule_type,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            calendar_config=calendar_config,
            timezone=timezone_str,
            parameters=parameters or {},
            start_date=start_date,
            end_date=end_date,
            created_by=created_by,
            is_enabled=True,
            run_count=0,
        )

        # Compute initial next_run_at
        job.next_run_at = self._compute_next_run(
            schedule_type=schedule_type,
            cron_expression=effective_cron,
            interval_seconds=interval_seconds,
            start_date=start_date,
        )

        self.db.add(job)
        await self.db.flush()
        return job

    async def get(self, job_id: UUID) -> ScheduledJob | None:
        result = await self.db.execute(
            select(ScheduledJob)
            .options(
                selectinload(ScheduledJob.automation),
                selectinload(ScheduledJob.creator),
            )
            .where(ScheduledJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self,
        enabled: bool | None = None,
        automation_id: UUID | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[ScheduledJob], int]:
        query = select(ScheduledJob).options(
            selectinload(ScheduledJob.automation),
            selectinload(ScheduledJob.creator),
        )

        if enabled is not None:
            query = query.where(ScheduledJob.is_enabled == enabled)
        if automation_id:
            query = query.where(ScheduledJob.automation_id == automation_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(ScheduledJob.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def update(
        self,
        job_id: UUID,
        name: str | None = None,
        description: str | None = None,
        schedule_type: str | None = None,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        calendar_config: dict | None = None,
        timezone_str: str | None = None,
        parameters: dict[str, Any] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ScheduledJob | None:
        job = await self.get(job_id)
        if not job:
            return None

        if name is not None:
            job.name = name
        if description is not None:
            job.description = description
        if timezone_str is not None:
            job.timezone = timezone_str
        if parameters is not None:
            job.parameters = parameters
        if start_date is not None:
            job.start_date = start_date
        if end_date is not None:
            job.end_date = end_date

        # If schedule changed, recompute next_run_at
        schedule_changed = False
        if schedule_type is not None:
            job.schedule_type = schedule_type
            schedule_changed = True
        if cron_expression is not None:
            job.cron_expression = cron_expression
            schedule_changed = True
        if interval_seconds is not None:
            job.interval_seconds = interval_seconds
            schedule_changed = True
        if calendar_config is not None:
            job.calendar_config = calendar_config
            schedule_changed = True

        if schedule_changed:
            effective_cron = self._resolve_cron_expression(
                job.schedule_type, job.cron_expression, job.interval_seconds, job.calendar_config
            )
            job.next_run_at = self._compute_next_run(
                schedule_type=job.schedule_type,
                cron_expression=effective_cron,
                interval_seconds=job.interval_seconds,
                start_date=job.start_date,
            )

        await self.db.flush()
        # Re-fetch to load server-side updated_at and relationships
        return await self.get(job_id)

    async def delete(self, job_id: UUID) -> bool:
        job = await self.get(job_id)
        if not job:
            return False
        await self.db.delete(job)
        await self.db.flush()
        return True

    async def toggle_enabled(self, job_id: UUID, enabled: bool) -> ScheduledJob | None:
        job = await self.get(job_id)
        if not job:
            return None

        job.is_enabled = enabled

        # Recompute next_run_at when re-enabling
        if enabled:
            effective_cron = self._resolve_cron_expression(
                job.schedule_type, job.cron_expression, job.interval_seconds, job.calendar_config
            )
            job.next_run_at = self._compute_next_run(
                schedule_type=job.schedule_type,
                cron_expression=effective_cron,
                interval_seconds=job.interval_seconds,
                start_date=job.start_date,
            )

        await self.db.flush()
        # Re-fetch to load server-side updated_at and relationships
        return await self.get(job_id)

    # ------------------------------------------------------------------
    # Schedule computation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_cron_expression(
        schedule_type: str,
        cron_expression: str | None,
        interval_seconds: int | None,
        calendar_config: dict | None,
    ) -> str | None:
        """Resolve any schedule type to an effective cron expression (or None for interval)."""
        if schedule_type == "cron":
            if not cron_expression:
                raise ValueError("cron_expression is required for cron schedule type")
            if not croniter.is_valid(cron_expression):
                raise ValueError(f"Invalid cron expression: {cron_expression}")
            return cron_expression

        if schedule_type == "interval":
            if not interval_seconds or interval_seconds < 60:
                raise ValueError("interval_seconds >= 60 is required for interval schedule type")
            return None  # interval uses simple datetime math

        if schedule_type == "calendar":
            if not calendar_config:
                raise ValueError("calendar_config is required for calendar schedule type")
            return ScheduledJobService._calendar_to_cron(calendar_config)

        raise ValueError(f"Unknown schedule_type: {schedule_type}")

    @staticmethod
    def _calendar_to_cron(config: dict) -> str:
        """Convert a CalendarConfig dict to a cron expression."""
        time_str = config.get("time", "09:00")
        parts = time_str.split(":")
        minute = int(parts[0]) if len(parts) > 1 else 0
        hour = int(parts[0]) if len(parts) > 1 else 9
        minute = int(parts[1]) if len(parts) > 1 else 0
        hour = int(parts[0])

        days_of_month = config.get("days_of_month", [])
        months = config.get("months", [])
        days_of_week = config.get("days_of_week", [])

        # Cron format: minute hour day-of-month month day-of-week
        dom = ",".join(str(d) for d in sorted(days_of_month)) if days_of_month else "*"
        mon = ",".join(str(m) for m in sorted(months)) if months else "*"
        # Cron uses 0=Sunday, but our API uses 0=Monday
        # Convert: Mon=0->1, Tue=1->2, ..., Sat=5->6, Sun=6->0
        cron_dow = [(d + 1) % 7 for d in days_of_week]
        dow = ",".join(str(d) for d in sorted(cron_dow)) if days_of_week else "*"

        cron = f"{minute} {hour} {dom} {mon} {dow}"
        if not croniter.is_valid(cron):
            raise ValueError(f"Generated invalid cron from calendar config: {cron}")
        return cron

    @staticmethod
    def _compute_next_run(
        schedule_type: str,
        cron_expression: str | None,
        interval_seconds: int | None,
        start_date: datetime | None = None,
        last_run_at: datetime | None = None,
    ) -> datetime | None:
        """Compute the next run time."""
        now = datetime.now(timezone.utc)
        base_time = max(now, start_date) if start_date and start_date > now else now

        if schedule_type == "interval":
            if not interval_seconds:
                return None
            if last_run_at:
                next_time = last_run_at + timedelta(seconds=interval_seconds)
                return next_time if next_time > now else now + timedelta(seconds=interval_seconds)
            return base_time + timedelta(seconds=interval_seconds)

        # cron or calendar (both use cron expression)
        if cron_expression:
            cron = croniter(cron_expression, base_time)
            return cron.get_next(datetime)

        return None
