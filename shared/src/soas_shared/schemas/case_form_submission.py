"""Case form submission schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.form_definition import FormDefinitionBrief
from soas_shared.schemas.user import UserBrief


class CaseFormSubmissionCreate(BaseSchema):
    form_definition_id: UUID
    data: dict[str, Any] = Field(description="Field key to value mapping")


class CaseFormSubmissionRead(BaseSchema):
    id: UUID
    case_id: UUID
    form_definition_id: UUID
    form_definition: FormDefinitionBrief
    data: dict[str, Any]
    is_evidence: bool = False
    submitted_by: UserBrief
    created_at: datetime
