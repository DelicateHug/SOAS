"""Code Library endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.code_library_service import CodeLibraryService
from soas_backend.services.version_service import VersionService
from soas_shared.schemas.version import VersionCreate, VersionRead, VersionUpdate
from soas_shared.schemas.code_library import (
    CodeLibraryBlockCreate,
    CodeLibraryBlockListItem,
    CodeLibraryBlockRead,
    CodeLibraryBlockUpdate,
    CodeLibraryPaletteEntry,
    CodeLibraryPermissionRead,
    CodeLibraryPermissionSet,
    CodeLibraryUserCategoryCreate,
    CodeLibraryUserCategoryRead,
    CodeLibraryUserCategoryUpdate,
)
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta

router = APIRouter(prefix="/code-library", tags=["code-library"])


def _to_read(block, is_favorited: bool = False) -> CodeLibraryBlockRead:
    from soas_shared.schemas.user import UserBrief
    creator = block.creator
    return CodeLibraryBlockRead(
        id=block.id,
        name=block.name,
        description=block.description,
        code=block.code,
        language=block.language,
        version=block.version,
        is_public=block.is_public,
        tags=block.tags or [],
        created_by=UserBrief(
            id=creator.id,
            username=creator.username,
            display_name=getattr(creator, "display_name", None) or creator.username,
        ),
        is_favorited=is_favorited,
        input_ports=block.input_ports,
        output_ports=block.output_ports,
        created_at=block.created_at,
        updated_at=block.updated_at,
    )


def _to_list_item(block, is_favorited: bool = False) -> CodeLibraryBlockListItem:
    from soas_shared.schemas.user import UserBrief
    creator = block.creator
    return CodeLibraryBlockListItem(
        id=block.id,
        name=block.name,
        description=block.description,
        language=block.language,
        version=block.version,
        is_public=block.is_public,
        tags=block.tags or [],
        created_by=UserBrief(
            id=creator.id,
            username=creator.username,
            display_name=getattr(creator, "display_name", None) or creator.username,
        ),
        is_favorited=is_favorited,
        input_ports=block.input_ports,
        output_ports=block.output_ports,
        created_at=block.created_at,
        updated_at=block.updated_at,
    )


@router.get("", response_model=PaginatedResponse[CodeLibraryBlockListItem])
async def list_blocks(
    search: str | None = Query(None),
    language: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    blocks, total = await svc.list_blocks(
        user_id=current_user.id,
        search=search,
        language=language,
        page=page,
        per_page=per_page,
    )
    favorites = await svc.get_user_favorites(current_user.id)
    return PaginatedResponse(
        data=[_to_list_item(b, b.id in favorites) for b in blocks],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )


@router.post("", response_model=CodeLibraryBlockRead, status_code=201)
async def create_block(
    body: CodeLibraryBlockCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.create(
        name=body.name,
        created_by=current_user.id,
        code=body.code,
        language=body.language,
        description=body.description,
        is_public=body.is_public,
        tags=body.tags,
        input_ports=[p.model_dump() for p in body.input_ports] if body.input_ports else None,
        output_ports=[p.model_dump() for p in body.output_ports] if body.output_ports else None,
    )
    return _to_read(block)


@router.get("/palette", response_model=list[CodeLibraryPaletteEntry])
async def get_palette(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    return await svc.get_palette_blocks(current_user.id)


@router.get("/favorites", response_model=list[CodeLibraryBlockListItem])
async def get_favorites(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    blocks, _ = await svc.list_blocks(user_id=current_user.id, per_page=500)
    favorites = await svc.get_user_favorites(current_user.id)
    fav_blocks = [b for b in blocks if b.id in favorites]
    return [_to_list_item(b, True) for b in fav_blocks]


@router.get("/categories", response_model=list[CodeLibraryUserCategoryRead])
async def get_categories(
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    cats = await svc.get_user_categories(current_user.id)
    return [
        CodeLibraryUserCategoryRead(
            id=c.id, name=c.name, parent_id=c.parent_id, sort_order=c.sort_order
        )
        for c in cats
    ]


@router.post("/categories", response_model=CodeLibraryUserCategoryRead, status_code=201)
async def create_category(
    body: CodeLibraryUserCategoryCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    cat = await svc.create_category(
        user_id=current_user.id,
        name=body.name,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    return CodeLibraryUserCategoryRead(
        id=cat.id, name=cat.name, parent_id=cat.parent_id, sort_order=cat.sort_order
    )


@router.patch("/categories/{category_id}", response_model=CodeLibraryUserCategoryRead)
async def update_category(
    category_id: UUID,
    body: CodeLibraryUserCategoryUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    cat = await svc.update_category(
        category_id=category_id,
        user_id=current_user.id,
        name=body.name,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return CodeLibraryUserCategoryRead(
        id=cat.id, name=cat.name, parent_id=cat.parent_id, sort_order=cat.sort_order
    )


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    if not await svc.delete_category(category_id, current_user.id):
        raise HTTPException(status_code=404, detail="Category not found")


@router.get("/{block_id}", response_model=CodeLibraryBlockRead)
async def get_block(
    block_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    is_fav = await svc.is_favorited(current_user.id, block_id)
    return _to_read(block, is_fav)


@router.patch("/{block_id}", response_model=CodeLibraryBlockRead)
async def update_block(
    block_id: UUID,
    body: CodeLibraryBlockUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if block.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can edit this block")
    updated = await svc.update(
        block_id,
        name=body.name,
        description=body.description,
        code=body.code,
        language=body.language,
        is_public=body.is_public,
        tags=body.tags,
        input_ports=[p.model_dump() for p in body.input_ports] if body.input_ports is not None else None,
        output_ports=[p.model_dump() for p in body.output_ports] if body.output_ports is not None else None,
    )
    is_fav = await svc.is_favorited(current_user.id, block_id)
    return _to_read(updated, is_fav)


@router.delete("/{block_id}", status_code=204)
async def delete_block(
    block_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if block.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this block")
    await svc.delete(block_id)


@router.get("/{block_id}/permissions", response_model=list[CodeLibraryPermissionRead])
async def get_permissions(
    block_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    perms = await svc.get_permissions(block_id)
    return [
        CodeLibraryPermissionRead(
            block_id=p.block_id,
            role_id=p.role_id,
            role_name=p.role.name if p.role else "",
            role_display_name=p.role.display_name if p.role else "",
            can_read=p.can_read,
            can_edit=p.can_edit,
            can_use=p.can_use,
        )
        for p in perms
    ]


@router.put("/{block_id}/permissions", response_model=list[CodeLibraryPermissionRead])
async def set_permissions(
    block_id: UUID,
    body: list[CodeLibraryPermissionSet],
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if block.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can manage permissions")
    await svc.set_permissions(
        block_id,
        [p.model_dump() for p in body],
        current_user.id,
    )
    perms = await svc.get_permissions(block_id)
    return [
        CodeLibraryPermissionRead(
            block_id=p.block_id,
            role_id=p.role_id,
            role_name=p.role.name if p.role else "",
            role_display_name=p.role.display_name if p.role else "",
            can_read=p.can_read,
            can_edit=p.can_edit,
            can_use=p.can_use,
        )
        for p in perms
    ]


@router.post("/{block_id}/favorite")
async def toggle_favorite(
    block_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    block = await svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    is_fav = await svc.toggle_favorite(current_user.id, block_id)
    return {"is_favorited": is_fav}


@router.put("/{block_id}/assign-category")
async def assign_category(
    block_id: UUID,
    category_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = CodeLibraryService(db)
    await svc.assign_block_to_category(current_user.id, block_id, category_id)
    return {"ok": True}


def _user_brief(user):
    from soas_shared.schemas.user import UserBrief
    if user is None:
        return None
    return UserBrief(
        id=user.id,
        username=user.username,
        display_name=getattr(user, "display_name", None) or user.username,
    )


def _version_read(v) -> VersionRead:
    return VersionRead(
        id=v.id,
        version_number=v.version_number,
        name=v.name,
        description=v.description,
        created_by=_user_brief(v.creator),
        created_at=v.created_at,
    )


# ------------------------------------------------------------------
# Version control endpoints
# ------------------------------------------------------------------


@router.get("/{block_id}/versions", response_model=list[VersionRead])
async def list_code_block_versions(
    block_id: UUID,
    _: dict = Depends(require_permission("code_library", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    versions = await svc.list_code_block_versions(block_id)
    return [_version_read(v) for v in versions]


@router.post("/{block_id}/versions", response_model=VersionRead, status_code=201)
async def create_code_block_version(
    block_id: UUID,
    body: VersionCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "update")),
    db: AsyncSession = Depends(get_db),
):
    code_svc = CodeLibraryService(db)
    block = await code_svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    svc = VersionService(db)
    version = await svc.create_code_block_version(
        block, current_user.id, name=body.name, description=body.description
    )
    return _version_read(version)


@router.patch("/{block_id}/versions/{version_number}", response_model=VersionRead)
async def update_code_block_version(
    block_id: UUID,
    version_number: int,
    body: VersionUpdate,
    _: dict = Depends(require_permission("code_library", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    version = await svc.update_code_block_version_meta(
        block_id, version_number, name=body.name, description=body.description
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return _version_read(version)


@router.post("/{block_id}/versions/{version_number}/restore", response_model=CodeLibraryBlockRead)
async def restore_code_block_version(
    block_id: UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("code_library", "update")),
    db: AsyncSession = Depends(get_db),
):
    code_svc = CodeLibraryService(db)
    block = await code_svc.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    svc = VersionService(db)
    block = await svc.restore_code_block_version(block, version_number)
    if not block:
        raise HTTPException(status_code=404, detail="Version not found")

    # Re-fetch with relationships
    block = await code_svc.get(block_id)
    is_fav = await code_svc.is_favorited(current_user.id, block_id)
    return _to_read(block, is_fav)
