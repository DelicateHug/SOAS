"""Case file attachment schemas."""

from datetime import datetime
from uuid import UUID

from soas_shared.schemas.common import BaseSchema
from soas_shared.schemas.user import UserBrief


class CaseFileRead(BaseSchema):
    id: UUID
    case_id: UUID
    filename: str
    content_type: str
    file_size: int
    description: str | None = None
    is_evidence: bool = False
    uploaded_by: UserBrief
    created_at: datetime
    expires_at: datetime | None = None
    can_delete: bool = False
