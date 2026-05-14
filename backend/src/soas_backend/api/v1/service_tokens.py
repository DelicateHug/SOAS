"""Service token management endpoints (admin only).

The raw token is shown exactly once — at create or rotate time. Subsequent reads only
return metadata + the prefix.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.service_token_service import ServiceTokenService

router = APIRouter(prefix="/service-tokens", tags=["service-tokens"])


class ServiceTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    user_id: UUID | None = Field(
        None,
        description="The user this token impersonates. Defaults to the current user.",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Permission strings (e.g. 'incident:read'). Empty = inherit user's perms.",
    )
    expires_at: datetime | None = None


class ServiceTokenRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    token_prefix: str
    user_id: UUID
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    last_used_ip: str | None
    created_at: datetime
    revoked_at: datetime | None


class ServiceTokenWithSecret(ServiceTokenRead):
    raw_token: str = Field(..., description="The raw bearer token. Shown ONCE only.")


def _to_read(t) -> ServiceTokenRead:
    return ServiceTokenRead(
        id=t.id,
        name=t.name,
        description=t.description,
        token_prefix=t.token_prefix,
        user_id=t.user_id,
        scopes=list(t.scopes or []),
        is_active=t.is_active,
        expires_at=t.expires_at,
        last_used_at=t.last_used_at,
        last_used_ip=t.last_used_ip,
        created_at=t.created_at,
        revoked_at=t.revoked_at,
    )


@router.get("", response_model=list[ServiceTokenRead])
async def list_service_tokens(
    include_revoked: bool = False,
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    svc = ServiceTokenService(db)
    return [_to_read(t) for t in await svc.list_tokens(include_revoked=include_revoked)]


@router.post("", response_model=ServiceTokenWithSecret, status_code=status.HTTP_201_CREATED)
async def create_service_token(
    body: ServiceTokenCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    target_user_id = body.user_id or current_user.id
    svc = ServiceTokenService(db)
    if await svc.get_by_name(body.name) is not None:
        raise HTTPException(status_code=409, detail="A service token with that name already exists")
    token, raw = await svc.create(
        name=body.name,
        user_id=target_user_id,
        description=body.description,
        scopes=body.scopes,
        expires_at=body.expires_at,
        created_by=current_user.id,
    )
    return ServiceTokenWithSecret(**_to_read(token).model_dump(), raw_token=raw)


@router.post("/{token_id}/rotate", response_model=ServiceTokenWithSecret)
async def rotate_service_token(
    token_id: UUID,
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    svc = ServiceTokenService(db)
    rotated = await svc.rotate(token_id)
    if rotated is None:
        raise HTTPException(status_code=404, detail="Token not found")
    token, raw = rotated
    return ServiceTokenWithSecret(**_to_read(token).model_dump(), raw_token=raw)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_service_token(
    token_id: UUID,
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    svc = ServiceTokenService(db)
    ok = await svc.revoke(token_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Token not found")
    return None
