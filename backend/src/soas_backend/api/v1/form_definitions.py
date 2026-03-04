"""Form definition CRUD endpoints."""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_permission
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.form_definition_service import FormDefinitionService
from soas_shared.schemas.common import PaginatedResponse, PaginationMeta
from soas_shared.schemas.form_definition import (
    FormDefinitionCreate,
    FormDefinitionRead,
    FormDefinitionUpdate,
    FormFieldSchema,
)
from soas_shared.schemas.user import UserBrief

router = APIRouter(tags=["form-definitions"])


def _user_brief(user) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(id=user.id, username=user.username, display_name=user.display_name)


def _defn_to_read(defn) -> FormDefinitionRead:
    return FormDefinitionRead(
        id=defn.id,
        name=defn.name,
        description=defn.description,
        fields=[FormFieldSchema(**f) for f in defn.fields],
        is_active=defn.is_active,
        created_by=_user_brief(defn.creator),
        updated_by=_user_brief(defn.updater),
        created_at=defn.created_at,
        updated_at=defn.updated_at,
    )


@router.get("/form-definitions")
async def list_form_definitions(
    active_only: bool = False,
    page: int = 1,
    per_page: int = 50,
    _: dict = Depends(require_permission("form_definition", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormDefinitionService(db)
    offset = (page - 1) * per_page
    definitions, total = await svc.list(active_only=active_only, offset=offset, limit=per_page)
    return PaginatedResponse(
        data=[_defn_to_read(d) for d in definitions],
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if per_page > 0 else 0,
        ),
    )


@router.get("/form-definitions/{definition_id}", response_model=FormDefinitionRead)
async def get_form_definition(
    definition_id: UUID,
    _: dict = Depends(require_permission("form_definition", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormDefinitionService(db)
    defn = await svc.get(definition_id)
    if not defn:
        raise HTTPException(status_code=404, detail="Form definition not found")
    return _defn_to_read(defn)


@router.post(
    "/form-definitions",
    response_model=FormDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_form_definition(
    body: FormDefinitionCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("form_definition", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormDefinitionService(db)
    defn = await svc.create(
        name=body.name,
        description=body.description,
        fields=[f.model_dump() for f in body.fields],
        created_by=current_user.id,
    )
    return _defn_to_read(defn)


@router.patch("/form-definitions/{definition_id}", response_model=FormDefinitionRead)
async def update_form_definition(
    definition_id: UUID,
    body: FormDefinitionUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("form_definition", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormDefinitionService(db)
    defn = await svc.get(definition_id)
    if not defn:
        raise HTTPException(status_code=404, detail="Form definition not found")

    update_fields = body.model_dump(exclude_unset=True)
    if "fields" in update_fields and update_fields["fields"] is not None:
        update_fields["fields"] = [f.model_dump() for f in body.fields]

    defn = await svc.update(definition_id, updated_by=current_user.id, **update_fields)
    return _defn_to_read(defn)


@router.delete(
    "/form-definitions/{definition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_form_definition(
    definition_id: UUID,
    _: dict = Depends(require_permission("form_definition", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = FormDefinitionService(db)
    defn = await svc.get(definition_id)
    if not defn:
        raise HTTPException(status_code=404, detail="Form definition not found")
    try:
        await svc.delete(definition_id)
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete form definition with existing submissions. Deactivate it instead.",
        )
    return None
