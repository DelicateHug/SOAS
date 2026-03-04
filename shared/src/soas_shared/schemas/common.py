"""Common schemas used across the API."""

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    status_code: int


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BaseReadSchema(BaseSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None
