"""Custom dashboards (Phase 2 of the case-managment port).

Distinct from /dashboard (singular) which is the legacy homepage stats
endpoint. /dashboards (plural) is the dashboard editor surface — CRUD
on dashboards and widgets, plus the widget render endpoint that
executes whitelisted queries.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.api.deps import (
    get_current_user,
    get_user_teams,
    require_permission,
)
from soas_backend.database import get_db
from soas_backend.models.user import User
from soas_backend.services.audit import audit
from soas_backend.services.dashboard_service import DashboardService
from soas_backend.services.widget_engine import WidgetEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


# ------------------------- schemas -------------------------


class WidgetRead(BaseModel):
    id: UUID
    title: str
    widget_type: str
    config: dict[str, Any]
    position: int
    width: int
    height: int

    model_config = {"from_attributes": True}


class DashboardRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_public: bool
    layout: dict[str, Any]
    owner_id: UUID
    team_id: UUID | None
    widgets: list[WidgetRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_public: bool = False
    team_id: UUID | None = None
    layout: dict[str, Any] | None = None


class DashboardUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    is_public: bool | None = None
    layout: dict[str, Any] | None = None
    team_id: UUID | None = None


class WidgetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    widget_type: str = Field(min_length=1, max_length=32)
    config: dict[str, Any] = Field(default_factory=dict)
    position: int = 0
    width: int = 6
    height: int = 2


class WidgetUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    config: dict[str, Any] | None = None
    position: int | None = None
    width: int | None = None
    height: int | None = None


# ------------------------- helpers -------------------------


def _team_ids_filter(teams: list[dict[str, Any]] | None) -> list[UUID] | None:
    if teams is None:
        return None  # admin = no filter
    return [UUID(t["id"]) for t in teams if t.get("id")]


def _can_edit(dash, user_id: UUID, is_admin: bool) -> bool:
    return is_admin or dash.owner_id == user_id


# ------------------------- routes -------------------------


@router.get("", response_model=list[DashboardRead])
async def list_dashboards(
    payload: dict = Depends(require_permission("dashboard", "read")),
    teams: list[dict[str, Any]] | None = Depends(get_user_teams),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    user_id = UUID(payload["sub"])
    dashboards = await svc.list_visible(user_id, _team_ids_filter(teams))
    # Strip widgets from list response to keep it small.
    return [
        DashboardRead(
            id=d.id, name=d.name, description=d.description, is_public=d.is_public,
            layout=d.layout, owner_id=d.owner_id, team_id=d.team_id, widgets=[],
        ) for d in dashboards
    ]


@router.get("/{dashboard_id}", response_model=DashboardRead)
async def get_dashboard(
    dashboard_id: UUID,
    _: dict = Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    dash = await svc.get(dashboard_id, include_widgets=True)
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dash


@router.post("", response_model=DashboardRead, status_code=201)
@audit(
    "dashboard.created",
    target_kind="dashboard",
    extract_target=lambda r: getattr(r, "id", None),
    extract_label=lambda r: getattr(r, "name", None),
)
async def create_dashboard(
    body: DashboardCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("dashboard", "create")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    dash = await svc.create(
        name=body.name,
        description=body.description,
        owner_id=current_user.id,
        team_id=body.team_id,
        is_public=body.is_public,
        layout=body.layout,
    )
    return DashboardRead(
        id=dash.id, name=dash.name, description=dash.description, is_public=dash.is_public,
        layout=dash.layout, owner_id=dash.owner_id, team_id=dash.team_id, widgets=[],
    )


@router.patch("/{dashboard_id}", response_model=DashboardRead)
async def update_dashboard(
    dashboard_id: UUID,
    body: DashboardUpdate,
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(require_permission("dashboard", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    existing = await svc.get(dashboard_id, include_widgets=False)
    if not existing:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    is_admin = "admin" in payload.get("roles", [])
    if not _can_edit(existing, current_user.id, is_admin):
        raise HTTPException(status_code=403, detail="Not the owner")
    fields = body.model_dump(exclude_unset=True)
    dash = await svc.update(dashboard_id, actor_id=current_user.id, **fields)
    return await svc.get(dash.id, include_widgets=True)


@router.delete("/{dashboard_id}", status_code=204)
async def delete_dashboard(
    dashboard_id: UUID,
    current_user: User = Depends(get_current_user),
    payload: dict = Depends(require_permission("dashboard", "delete")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    existing = await svc.get(dashboard_id, include_widgets=False)
    if not existing:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    is_admin = "admin" in payload.get("roles", [])
    if not _can_edit(existing, current_user.id, is_admin):
        raise HTTPException(status_code=403, detail="Not the owner")
    await svc.delete(dashboard_id, actor_id=current_user.id)


# ----- Widgets -----


@router.post("/{dashboard_id}/widgets", response_model=WidgetRead, status_code=201)
async def add_widget(
    dashboard_id: UUID,
    body: WidgetCreate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("dashboard", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    dash = await svc.get(dashboard_id, include_widgets=False)
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    widget = await svc.add_widget(
        dashboard_id=dashboard_id,
        title=body.title,
        widget_type=body.widget_type,
        config=body.config,
        position=body.position,
        width=body.width,
        height=body.height,
        actor_id=current_user.id,
    )
    return widget


@router.patch("/widgets/{widget_id}", response_model=WidgetRead)
async def update_widget(
    widget_id: UUID,
    body: WidgetUpdate,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("dashboard", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    fields = body.model_dump(exclude_unset=True)
    widget = await svc.update_widget(widget_id, actor_id=current_user.id, **fields)
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    return widget


@router.delete("/widgets/{widget_id}", status_code=204)
async def delete_widget(
    widget_id: UUID,
    current_user: User = Depends(get_current_user),
    _: dict = Depends(require_permission("dashboard", "update")),
    db: AsyncSession = Depends(get_db),
):
    svc = DashboardService(db)
    deleted = await svc.delete_widget(widget_id, actor_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Widget not found")


# ----- Widget render (the data endpoint) -----


@router.post("/render-widget")
async def render_widget(
    body: WidgetCreate,
    _: dict = Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Execute the widget query without saving. Used by the live editor."""
    engine = WidgetEngine(db)
    try:
        return await engine.execute(body.widget_type, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/widgets/{widget_id}/data")
async def widget_data(
    widget_id: UUID,
    _: dict = Depends(require_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a saved widget's data. Used by the read-only dashboard view."""
    from sqlalchemy import select

    from soas_backend.models.dashboard import DashboardWidget

    result = await db.execute(select(DashboardWidget).where(DashboardWidget.id == widget_id))
    widget = result.scalar_one_or_none()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    engine = WidgetEngine(db)
    try:
        return await engine.execute(widget.widget_type, widget.config or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
