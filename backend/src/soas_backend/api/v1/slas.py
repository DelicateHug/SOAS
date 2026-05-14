"""SLA admin + read API (Phase 5)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import require_role
from soas_backend.database import get_db
from soas_backend.models.sla import SLADefinition, SLASnapshot
from soas_backend.services.sla_service import (
    SLAService,
    VALID_DIMENSIONS,
    VALID_END_COLUMNS,
)

router = APIRouter(prefix="/slas", tags=["slas"])


class DefRead(BaseModel):
    id: UUID
    key: str
    label: str
    description: str | None
    start_column: str
    end_column: str
    target_seconds: int
    dimension: str
    is_enabled: bool

    model_config = {"from_attributes": True}


class DefCreate(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_column: str = "created_at"
    end_column: str
    target_seconds: int = Field(gt=0)
    dimension: str = "(global)"
    is_enabled: bool = True


class DefUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    target_seconds: int | None = None
    dimension: str | None = None
    is_enabled: bool | None = None


class SnapshotRead(BaseModel):
    sla_key: str
    dim_value: str
    captured_for: date
    total_count: int
    compliant_count: int
    compliance_pct: float
    p50_seconds: float | None
    p95_seconds: float | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[DefRead])
async def list_definitions(
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    return await SLAService(db).list_definitions()


@router.post("", response_model=DefRead, status_code=201)
async def create_definition(
    body: DefCreate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    if body.end_column not in VALID_END_COLUMNS:
        raise HTTPException(status_code=400, detail=f"end_column must be one of {sorted(VALID_END_COLUMNS)}")
    if body.dimension not in VALID_DIMENSIONS:
        raise HTTPException(status_code=400, detail=f"dimension must be one of {sorted(VALID_DIMENSIONS)}")
    sla = SLADefinition(**body.model_dump())
    db.add(sla)
    await db.flush()
    return sla


@router.patch("/{sla_id}", response_model=DefRead)
async def update_definition(
    sla_id: UUID,
    body: DefUpdate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SLADefinition).where(SLADefinition.id == sla_id))
    sla = result.scalar_one_or_none()
    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")
    fields = body.model_dump(exclude_unset=True)
    if "dimension" in fields and fields["dimension"] not in VALID_DIMENSIONS:
        raise HTTPException(status_code=400, detail="invalid dimension")
    for k, v in fields.items():
        setattr(sla, k, v)
    await db.flush()
    return sla


@router.delete("/{sla_id}", status_code=204)
async def delete_definition(
    sla_id: UUID,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(SLADefinition).where(SLADefinition.id == sla_id))
    sla = result.scalar_one_or_none()
    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")
    await db.delete(sla)


@router.get("/snapshots", response_model=list[SnapshotRead])
async def list_snapshots(
    sla_key: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    snaps = await SLAService(db).recent_snapshots(sla_key=sla_key, days=days)
    return snaps


@router.post("/recompute", status_code=202)
async def recompute(
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Synchronous on-demand snapshot recomputation (small dataset)."""
    return await SLAService(db).compute_all()
