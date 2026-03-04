"""Automation schemas."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.constants import AutomationStatus
from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


class AutomationInputType(StrEnum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    LIST = "LIST"
    DICT = "DICT"
    ANY = "ANY"


class AutomationInputDef(BaseSchema):
    """Definition of a single typed input for an automation."""
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    type: AutomationInputType = AutomationInputType.STRING
    required: bool = True
    default_value: Any = None
    description: str = ""


class AutomationCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    graph_data: dict[str, Any] | None = None
    parameters: list[AutomationInputDef] = []
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    tags: list[str] = []
    trigger_tags: list[str] = []
    is_trigger_enabled: bool = False


class AutomationRead(BaseReadSchema):
    name: str
    description: str | None = None
    status: AutomationStatus
    graph_file: str | None = None
    graph_data: dict[str, Any] | None = None
    script_hash: str | None = None
    version: int
    parameters: list[AutomationInputDef] = []
    timeout_seconds: int
    created_by: UserBrief
    tags: list[str] = []
    trigger_tags: list[str] = []
    is_trigger_enabled: bool = False
    documentation: str | None = None


class AutomationUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    status: AutomationStatus | None = None
    parameters: list[AutomationInputDef] | None = None
    timeout_seconds: int | None = Field(default=None, ge=10, le=3600)
    tags: list[str] | None = None
    trigger_tags: list[str] | None = None
    is_trigger_enabled: bool | None = None
    documentation: str | None = None


class AutomationExecuteRequest(BaseSchema):
    parameters: dict[str, Any] = {}
    incident_id: UUID | None = None
    case_id: UUID | None = None


class AutomationPermissionRead(BaseSchema):
    automation_id: UUID
    role_id: UUID
    role_name: str
    can_read: bool
    can_execute: bool
    can_edit: bool
    can_add: bool


class AutomationPermissionSet(BaseSchema):
    role_id: UUID
    can_read: bool = False
    can_execute: bool = True
    can_edit: bool = False
    can_add: bool = False


class AutomationListItem(BaseReadSchema):
    name: str
    description: str | None = None
    status: AutomationStatus
    version: int
    created_by: UserBrief
    tags: list[str] = []
    parameters: list[AutomationInputDef] = []
