"""Normalization schemas."""

from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema


class NormalizationGroupRead(BaseSchema):
    id: UUID
    name: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    display_order: int


class NormalizationRuleCreate(BaseSchema):
    group_id: UUID
    source_path: str = Field(min_length=1, max_length=500)
    target_field: str = Field(min_length=1, max_length=200)
    transform_type: str = Field(default="direct", max_length=20)
    transform_config: dict[str, Any] = {}
    is_required: bool = False
    default_value: Any | None = None
    display_order: int = 0
    is_enabled: bool = True


class NormalizationRuleUpdate(BaseSchema):
    group_id: UUID | None = None
    source_path: str | None = None
    target_field: str | None = None
    transform_type: str | None = None
    transform_config: dict[str, Any] | None = None
    is_required: bool | None = None
    default_value: Any = None
    display_order: int | None = None
    is_enabled: bool | None = None


class NormalizationRuleRead(BaseReadSchema):
    group_id: UUID
    group: NormalizationGroupRead | None = None
    source_path: str
    target_field: str
    transform_type: str
    transform_config: dict[str, Any] = {}
    is_required: bool
    default_value: Any | None = None
    display_order: int
    is_enabled: bool


class NormalizationBulkSave(BaseSchema):
    rules: list[NormalizationRuleCreate]


class NormalizationTestRequest(BaseSchema):
    raw_payload: dict[str, Any]


class NormalizationTestResponse(BaseSchema):
    normalized: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []
