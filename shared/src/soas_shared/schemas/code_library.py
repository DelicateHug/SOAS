"""Code Library schemas."""

from typing import Any
from uuid import UUID

from pydantic import Field

from soas_shared.schemas.common import BaseReadSchema, BaseSchema
from soas_shared.schemas.user import UserBrief


class CodeBlockPortDef(BaseSchema):
    """Definition of a single port on a code library block."""
    name: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    type: str = Field(pattern=r"^(FLOW|STRING|INTEGER|FLOAT|BOOLEAN|LIST|DICT|OBJECT|ANY)$")
    description: str = ""
    required: bool = False


class CodeLibraryBlockCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    code: str = ""
    language: str = Field(default="python", pattern=r"^(python|javascript|bash)$")
    is_public: bool = False
    tags: list[str] = []
    input_ports: list[CodeBlockPortDef] | None = None
    output_ports: list[CodeBlockPortDef] | None = None


class CodeLibraryBlockRead(BaseReadSchema):
    name: str
    description: str | None = None
    code: str
    language: str
    version: int
    is_public: bool
    tags: list[str] = []
    created_by: UserBrief
    is_favorited: bool = False
    input_ports: list[dict[str, Any]] | None = None
    output_ports: list[dict[str, Any]] | None = None


class CodeLibraryBlockUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    code: str | None = None
    language: str | None = Field(default=None, pattern=r"^(python|javascript|bash)$")
    is_public: bool | None = None
    tags: list[str] | None = None
    input_ports: list[CodeBlockPortDef] | None = None
    output_ports: list[CodeBlockPortDef] | None = None


class CodeLibraryBlockListItem(BaseReadSchema):
    name: str
    description: str | None = None
    language: str
    version: int
    is_public: bool
    tags: list[str] = []
    created_by: UserBrief
    is_favorited: bool = False
    input_ports: list[dict[str, Any]] | None = None
    output_ports: list[dict[str, Any]] | None = None


class CodeLibraryPermissionRead(BaseSchema):
    block_id: UUID
    role_id: UUID
    role_name: str
    role_display_name: str = ""
    can_read: bool
    can_edit: bool
    can_use: bool


class CodeLibraryPermissionSet(BaseSchema):
    role_id: UUID
    can_read: bool = True
    can_edit: bool = False
    can_use: bool = True


class CodeLibraryUserCategoryRead(BaseSchema):
    id: UUID
    name: str
    parent_id: UUID | None = None
    sort_order: int = 0


class CodeLibraryUserCategoryCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=100)
    parent_id: UUID | None = None
    sort_order: int = 0


class CodeLibraryUserCategoryUpdate(BaseSchema):
    name: str | None = None
    parent_id: UUID | None = None
    sort_order: int | None = None


class CodeLibraryPaletteEntry(BaseSchema):
    """A library block formatted for the NodePalette."""
    type: str
    name: str
    category: str = "Custom"
    subcategory: str | None = None
    color: str = "#4CAF50"
    description: str = ""
    icon: str | None = None
    input_ports: list[dict[str, Any]] = []
    output_ports: list[dict[str, Any]] = []
    properties: list[dict[str, Any]] = []
    is_library_block: bool = True
    library_block_id: UUID
    library_block_version: int
    is_favorited: bool = False
    creator_name: str = ""
