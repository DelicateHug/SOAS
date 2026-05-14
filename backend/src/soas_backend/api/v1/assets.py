"""Asset inventory + detection (Phase 6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.asset import Asset
from soas_backend.models.user import User

router = APIRouter(prefix="/assets", tags=["assets"])

ASSET_TYPES = ("user", "host", "ip", "account")

# Each asset type maps to a default key inside Incident.metadata_ to scan.
DETECT_METADATA_KEYS = {
    "user": ("username",),
    "host": ("hostname",),
    "ip": ("src_ip", "dest_ip"),
    "account": ("username", "account"),
}

TIMEFRAMES = {
    "last_24h": timedelta(hours=24),
    "last_7d": timedelta(days=7),
    "last_30d": timedelta(days=30),
    "last_90d": timedelta(days=90),
}


# ----- schemas -----


class AssetRead(BaseModel):
    id: UUID
    asset_type: str
    identifier: str
    label: str | None
    description: str | None
    tags: list[str]
    team_id: UUID | None
    owner_id: UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class AssetCreate(BaseModel):
    asset_type: str
    identifier: str = Field(min_length=1, max_length=500)
    label: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    team_id: UUID | None = None
    owner_id: UUID | None = None


class AssetUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    team_id: UUID | None = None
    owner_id: UUID | None = None
    is_active: bool | None = None


# ----- routes -----


@router.get("", response_model=list[AssetRead])
async def list_assets(
    asset_type: str | None = Query(None),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    q = select(Asset).order_by(Asset.asset_type.asc(), Asset.identifier.asc())
    if asset_type:
        if asset_type not in ASSET_TYPES:
            raise HTTPException(status_code=400, detail="Unknown asset_type")
        q = q.where(Asset.asset_type == asset_type)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=AssetRead, status_code=201)
async def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    if body.asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"asset_type must be one of {ASSET_TYPES}")
    asset = Asset(
        asset_type=body.asset_type,
        identifier=body.identifier,
        label=body.label,
        description=body.description,
        tags=body.tags,
        team_id=body.team_id,
        owner_id=body.owner_id,
        created_by=current_user.id,
    )
    db.add(asset)
    await db.flush()
    return asset


@router.patch("/{asset_id}", response_model=AssetRead)
async def update_asset(
    asset_id: UUID,
    body: AssetUpdate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    await db.flush()
    return a


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    await db.delete(a)


@router.get("/{asset_id}/detect")
async def detect_asset(
    asset_id: UUID,
    timeframe: str = Query("last_30d"),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    """Find recent incidents that referenced this asset by metadata key."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Unknown timeframe")

    since = datetime.now(timezone.utc) - TIMEFRAMES[timeframe]
    keys = DETECT_METADATA_KEYS.get(a.asset_type, ())
    if not keys:
        return {"data": [], "meta": {"asset_id": str(a.id), "since": since.isoformat()}}

    # Build an OR over metadata_->>key = identifier
    or_clauses = " OR ".join([f"metadata->>'{k}' = :ident" for k in keys])
    sql = f"""
        SELECT id, title, severity, status, created_at
        FROM incidents
        WHERE created_at >= :since
          AND ({or_clauses})
        ORDER BY created_at DESC
        LIMIT 200
    """
    rs = await db.execute(text(sql), {"since": since, "ident": a.identifier})
    rows = [
        {
            "id": str(r.id),
            "title": r.title,
            "severity": r.severity,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rs.all()
    ]
    return {"data": rows, "meta": {"asset_id": str(a.id), "since": since.isoformat(), "count": len(rows)}}
