"""Phase 10 observability endpoints: cluster samples, page-load beacon, network IO ingest."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import get_current_user, require_role
from soas_backend.database import get_db
from soas_backend.models.observability import (
    InstanceMetricSample,
    NetworkIOMinutely,
    PageLoadSample,
)
from soas_backend.models.user import User

router = APIRouter(prefix="/observability", tags=["observability"])


# ----------------------------- cluster -----------------------------


class InstanceMetricRead(BaseModel):
    instance_id: str
    role: str | None
    cpu_pct: float | None
    mem_pct: float | None
    mem_rss_bytes: int | None
    net_in_bytes: int | None
    net_out_bytes: int | None
    uptime_seconds: int | None
    version: str | None
    captured_at: datetime

    model_config = {"from_attributes": True}


class InstanceMetricCreate(BaseModel):
    instance_id: str
    role: str | None = None
    cpu_pct: float | None = None
    mem_pct: float | None = None
    mem_rss_bytes: int | None = None
    net_in_bytes: int | None = None
    net_out_bytes: int | None = None
    uptime_seconds: int | None = None
    version: str | None = None


@router.get("/cluster", response_model=list[InstanceMetricRead])
async def cluster_samples(
    since_minutes: int = Query(15, ge=1, le=720),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    """Per-instance samples within the last `since_minutes` window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    rs = await db.execute(
        select(InstanceMetricSample)
        .where(InstanceMetricSample.captured_at >= cutoff)
        .order_by(InstanceMetricSample.captured_at.desc())
        .limit(1000)
    )
    return list(rs.scalars().all())


@router.post("/cluster/samples", status_code=204)
async def push_cluster_sample(
    body: InstanceMetricCreate,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Worker heartbeat task posts here. Best-effort, no response."""
    db.add(InstanceMetricSample(**body.model_dump()))
    await db.flush()


# ----------------------------- network IO -----------------------------


class NetworkIORollup(BaseModel):
    minute_utc: datetime
    source: str
    bytes_in: int
    bytes_out: int
    request_count: int
    error_count: int


class NetworkIOIngest(BaseModel):
    """One per-minute roll-up bucket. Caller (any backend/worker that monkey-
    patches httpx) flushes accumulated counts every ~10s; this endpoint
    upserts into the minutely row."""
    minute_utc: datetime
    source: str = Field(min_length=1, max_length=64)
    bytes_in: int = 0
    bytes_out: int = 0
    request_count: int = 0
    error_count: int = 0


@router.post("/network-io/ingest", status_code=204)
async def network_io_ingest(
    body: NetworkIOIngest,
    _: dict = Depends(require_role("admin", "soc_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Upsert a (minute, source) network IO row."""
    minute = body.minute_utc.replace(second=0, microsecond=0)
    # Upsert via raw SQL — ON CONFLICT on the unique index.
    await db.execute(
        text("""
            INSERT INTO network_io_minutely (minute_utc, source, bytes_in, bytes_out, request_count, error_count)
            VALUES (:m, :s, :bi, :bo, :rc, :ec)
            ON CONFLICT (minute_utc, source) DO UPDATE SET
              bytes_in = network_io_minutely.bytes_in + EXCLUDED.bytes_in,
              bytes_out = network_io_minutely.bytes_out + EXCLUDED.bytes_out,
              request_count = network_io_minutely.request_count + EXCLUDED.request_count,
              error_count = network_io_minutely.error_count + EXCLUDED.error_count
        """),
        {
            "m": minute, "s": body.source, "bi": body.bytes_in, "bo": body.bytes_out,
            "rc": body.request_count, "ec": body.error_count,
        },
    )


@router.get("/network-io", response_model=list[NetworkIORollup])
async def network_io_recent(
    since_hours: int = Query(24, ge=1, le=168),
    _: dict = Depends(require_role("admin", "soc_manager", "analyst")),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    rs = await db.execute(
        select(NetworkIOMinutely)
        .where(NetworkIOMinutely.minute_utc >= cutoff)
        .order_by(NetworkIOMinutely.minute_utc.desc())
        .limit(5000)
    )
    return list(rs.scalars().all())


# ----------------------------- page load -----------------------------


class PerfNonce(BaseModel):
    nonce: str
    path: str


class PerfBeacon(BaseModel):
    nonce: str
    ttfb_ms: int | None = None
    dom_ready_ms: int | None = None
    load_ms: int | None = None


@router.post("/perf/nonce", response_model=PerfNonce)
async def issue_nonce(
    path: str = Query(..., min_length=1, max_length=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Issue a beacon nonce. Frontend includes it in the page meta and posts back via /perf/beacon."""
    nonce = secrets.token_urlsafe(16)
    db.add(PageLoadSample(nonce=nonce, path=path[:500], user_id=current_user.id))
    await db.flush()
    return PerfNonce(nonce=nonce, path=path)


@router.post("/perf/beacon", status_code=204)
async def post_beacon(body: PerfBeacon, db: AsyncSession = Depends(get_db)):
    """Browser posts timings back here. Unauth'd (we don't trust user-side anyway)."""
    rs = await db.execute(select(PageLoadSample).where(PageLoadSample.nonce == body.nonce))
    sample = rs.scalar_one_or_none()
    if not sample:
        # Beacon may arrive before the nonce row in some races; create an
        # orphan and let a future flush merge.
        sample = PageLoadSample(
            nonce=body.nonce,
            path="(orphan)",
            ttfb_ms=body.ttfb_ms,
            dom_ready_ms=body.dom_ready_ms,
            load_ms=body.load_ms,
        )
        db.add(sample)
    else:
        sample.ttfb_ms = body.ttfb_ms
        sample.dom_ready_ms = body.dom_ready_ms
        sample.load_ms = body.load_ms
    await db.flush()
