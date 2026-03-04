"""Scheduled job schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from soas_shared.constants import ScheduleType
from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


class CalendarConfig(BaseSchema):
    """Rich calendar-based scheduling configuration."""

    days_of_week: list[int] = Field(default=[], description="0=Mon..6=Sun")
    days_of_month: list[int] = Field(default=[], description="1-31")
    months: list[int] = Field(default=[], description="1-12, empty=all")
    time: str = Field(default="09:00", description="HH:MM in 24h format")

    @field_validator("days_of_week", mode="before")
    @classmethod
    def validate_days_of_week(cls, v: list[int]) -> list[int]:
        for d in v:
            if d < 0 or d > 6:
                raise ValueError(f"day_of_week must be 0-6, got {d}")
        return sorted(set(v))

    @field_validator("days_of_month", mode="before")
    @classmethod
    def validate_days_of_month(cls, v: list[int]) -> list[int]:
        for d in v:
            if d < 1 or d > 31:
                raise ValueError(f"day_of_month must be 1-31, got {d}")
        return sorted(set(v))

    @field_validator("months", mode="before")
    @classmethod
    def validate_months(cls, v: list[int]) -> list[int]:
        for m in v:
            if m < 1 or m > 12:
                raise ValueError(f"month must be 1-12, got {m}")
        return sorted(set(v))

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("time must be HH:MM format")
        h, m = int(parts[0]), int(parts[1])
        if h < 0 or h > 23 or m < 0 or m > 59:
            raise ValueError("invalid time")
        return v


class ScheduledJobCreate(BaseSchema):
    automation_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    schedule_type: ScheduleType
    cron_expression: str | None = Field(default=None, max_length=100)
    interval_seconds: int | None = Field(default=None, ge=60, le=86400 * 365)
    calendar_config: CalendarConfig | None = None
    timezone: str = "UTC"
    parameters: dict[str, Any] = {}
    start_date: datetime | None = None
    end_date: datetime | None = None


class ScheduledJobUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    schedule_type: ScheduleType | None = None
    cron_expression: str | None = Field(default=None, max_length=100)
    interval_seconds: int | None = Field(default=None, ge=60, le=86400 * 365)
    calendar_config: CalendarConfig | None = None
    timezone: str | None = None
    parameters: dict[str, Any] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class ScheduledJobRead(BaseReadSchema):
    automation_id: UUID
    automation_name: str
    name: str
    description: str | None = None
    schedule_type: ScheduleType
    cron_expression: str | None = None
    interval_seconds: int | None = None
    calendar_config: CalendarConfig | None = None
    timezone: str
    parameters: dict[str, Any] = {}
    is_enabled: bool
    start_date: datetime | None = None
    end_date: datetime | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    run_count: int
    created_by: UserBrief


class ScheduledJobListItem(BaseReadSchema):
    automation_id: UUID
    automation_name: str
    name: str
    description: str | None = None
    schedule_type: ScheduleType
    cron_expression: str | None = None
    interval_seconds: int | None = None
    calendar_config: CalendarConfig | None = None
    timezone: str
    is_enabled: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    run_count: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_by: UserBrief
