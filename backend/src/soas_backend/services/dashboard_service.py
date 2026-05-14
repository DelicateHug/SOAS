"""Dashboard + widget CRUD + visibility checks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.dashboard import Dashboard, DashboardWidget
from soas_backend.services.artifact_change_service import ArtifactChangeService


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = ArtifactChangeService(db)

    # ------------------------- list / get -------------------------

    async def list_visible(self, user_id: UUID, team_ids: list[UUID] | None) -> list[Dashboard]:
        q = select(Dashboard).order_by(Dashboard.updated_at.desc())
        if team_ids is None:
            # Admin or "all teams" — no filter
            pass
        else:
            q = q.where(
                or_(
                    Dashboard.is_public.is_(True),
                    Dashboard.owner_id == user_id,
                    Dashboard.team_id.in_(team_ids) if team_ids else False,
                )
            )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get(self, dashboard_id: UUID, *, include_widgets: bool = True) -> Dashboard | None:
        q = select(Dashboard).where(Dashboard.id == dashboard_id)
        if include_widgets:
            q = q.options(selectinload(Dashboard.widgets))
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    # ------------------------- CRUD -------------------------

    async def create(
        self,
        *,
        name: str,
        description: str | None,
        owner_id: UUID,
        team_id: UUID | None = None,
        is_public: bool = False,
        layout: dict[str, Any] | None = None,
    ) -> Dashboard:
        dash = Dashboard(
            name=name,
            description=description,
            owner_id=owner_id,
            team_id=team_id,
            is_public=is_public,
            layout=layout or {},
        )
        self.db.add(dash)
        await self.db.flush()
        await self.audit.record(
            kind="dashboard", action="create", target_id=dash.id, target_label=name, actor_id=owner_id
        )
        return dash

    async def update(
        self,
        dashboard_id: UUID,
        *,
        actor_id: UUID,
        name: str | None = None,
        description: str | None = None,
        is_public: bool | None = None,
        layout: dict[str, Any] | None = None,
        team_id: UUID | None = ...,  # type: ignore[assignment]
    ) -> Dashboard | None:
        dash = await self.get(dashboard_id, include_widgets=False)
        if not dash:
            return None
        if name is not None:
            dash.name = name
        if description is not None:
            dash.description = description
        if is_public is not None:
            dash.is_public = is_public
        if layout is not None:
            dash.layout = layout
        if team_id is not ...:
            dash.team_id = team_id
        await self.db.flush()
        await self.audit.record(
            kind="dashboard", action="update", target_id=dash.id, target_label=dash.name, actor_id=actor_id
        )
        return dash

    async def delete(self, dashboard_id: UUID, *, actor_id: UUID) -> bool:
        dash = await self.get(dashboard_id, include_widgets=False)
        if not dash:
            return False
        label = dash.name
        await self.db.delete(dash)
        await self.audit.record(
            kind="dashboard", action="delete", target_id=dashboard_id, target_label=label, actor_id=actor_id
        )
        return True

    # ------------------------- widgets -------------------------

    async def add_widget(
        self,
        *,
        dashboard_id: UUID,
        title: str,
        widget_type: str,
        config: dict[str, Any],
        position: int = 0,
        width: int = 6,
        height: int = 2,
        actor_id: UUID,
    ) -> DashboardWidget:
        widget = DashboardWidget(
            dashboard_id=dashboard_id,
            title=title,
            widget_type=widget_type,
            config=config,
            position=position,
            width=width,
            height=height,
        )
        self.db.add(widget)
        await self.db.flush()
        await self.audit.record(
            kind="widget", action="create", target_id=widget.id, target_label=title, actor_id=actor_id,
            extra={"dashboard_id": str(dashboard_id), "widget_type": widget_type},
        )
        return widget

    async def update_widget(
        self,
        widget_id: UUID,
        *,
        actor_id: UUID,
        title: str | None = None,
        config: dict[str, Any] | None = None,
        position: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> DashboardWidget | None:
        result = await self.db.execute(
            select(DashboardWidget).where(DashboardWidget.id == widget_id)
        )
        widget = result.scalar_one_or_none()
        if not widget:
            return None
        if title is not None:
            widget.title = title
        if config is not None:
            widget.config = config
        if position is not None:
            widget.position = position
        if width is not None:
            widget.width = width
        if height is not None:
            widget.height = height
        await self.db.flush()
        await self.audit.record(
            kind="widget", action="update", target_id=widget.id, target_label=widget.title, actor_id=actor_id
        )
        return widget

    async def delete_widget(self, widget_id: UUID, *, actor_id: UUID) -> bool:
        result = await self.db.execute(
            select(DashboardWidget).where(DashboardWidget.id == widget_id)
        )
        widget = result.scalar_one_or_none()
        if not widget:
            return False
        title = widget.title
        await self.db.delete(widget)
        await self.audit.record(
            kind="widget", action="delete", target_id=widget_id, target_label=title, actor_id=actor_id
        )
        return True
