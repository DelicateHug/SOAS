"""Form definition schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.user import UserBrief


class FormFieldSchema(BaseSchema):
    """Schema for a single field in a form definition."""

    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    type: str = Field(description="text, textarea, number, select, checkbox, date")
    required: bool = False
    options: list[str] = []
    placeholder: str | None = None
    help_text: str | None = None


class FormDefinitionCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=300)
    description: str | None = None
    fields: list[FormFieldSchema] = Field(min_length=1)


class FormDefinitionUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    fields: list[FormFieldSchema] | None = None
    is_active: bool | None = None


class FormDefinitionRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    fields: list[FormFieldSchema]
    is_active: bool
    created_by: UserBrief
    updated_by: UserBrief | None = None
    created_at: datetime
    updated_at: datetime


class FormDefinitionBrief(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    is_active: bool
