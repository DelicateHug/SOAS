"""Seed a default Operations dashboard on first boot.

Idempotent: only runs once. The dashboard is owned by the first admin
user found and is marked public so every signed-in user can read it.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.dashboard import Dashboard, DashboardWidget
from soas_backend.models.user import User

logger = logging.getLogger(__name__)

SEED_NAME = "SOC Operations Overview"


WIDGETS: list[dict] = [
    {
        "title": "Incidents (last 7d)",
        "widget_type": "counter",
        "config": {"source": "incidents", "time_range": "last_7d"},
        "position": 0,
        "width": 3,
        "height": 2,
    },
    {
        "title": "Open cases",
        "widget_type": "counter",
        "config": {"source": "cases", "time_range": "last_30d"},
        "position": 1,
        "width": 3,
        "height": 2,
    },
    {
        "title": "Token spend (last 7d)",
        "widget_type": "tokens_counter",
        "config": {"time_range": "last_7d", "metric": "cost_usd"},
        "position": 2,
        "width": 3,
        "height": 2,
    },
    {
        "title": "Executions (last 7d)",
        "widget_type": "counter",
        "config": {"source": "executions", "time_range": "last_7d"},
        "position": 3,
        "width": 3,
        "height": 2,
    },
    {
        "title": "Incidents by severity",
        "widget_type": "pie",
        "config": {
            "source": "incidents",
            "time_range": "last_30d",
            "dimension": "severity",
            "limit": 8,
        },
        "position": 4,
        "width": 6,
        "height": 3,
    },
    {
        "title": "Incidents over time",
        "widget_type": "timeseries",
        "config": {
            "source": "incidents",
            "time_range": "last_30d",
            "bucket": "day",
        },
        "position": 5,
        "width": 6,
        "height": 3,
    },
    {
        "title": "Top alert categories",
        "widget_type": "top_n",
        "config": {
            "source": "incidents",
            "time_range": "last_30d",
            "dimension": "category_key",
            "limit": 10,
        },
        "position": 6,
        "width": 6,
        "height": 3,
    },
    {
        "title": "Token usage by caller",
        "widget_type": "tokens_top_n",
        "config": {
            "time_range": "last_30d",
            "dimension": "caller",
            "metric": "cost_usd",
            "limit": 10,
        },
        "position": 7,
        "width": 6,
        "height": 3,
    },
    {
        "title": "Artifact changes by kind",
        "widget_type": "changes_top_n",
        "config": {
            "time_range": "last_30d",
            "dimension": "kind",
            "limit": 12,
        },
        "position": 8,
        "width": 6,
        "height": 3,
    },
    {
        "title": "Changes over time",
        "widget_type": "changes_timeseries",
        "config": {"time_range": "last_30d", "bucket": "day"},
        "position": 9,
        "width": 6,
        "height": 3,
    },
]


async def seed_default_dashboard(db: AsyncSession) -> Dashboard | None:
    rs = await db.execute(select(Dashboard).where(Dashboard.name == SEED_NAME))
    existing = rs.scalar_one_or_none()
    if existing:
        return existing

    # Pick the first admin user as owner — falls back to the first user.
    rs = await db.execute(select(User).order_by(User.created_at.asc()).limit(1))
    owner = rs.scalar_one_or_none()
    if owner is None:
        logger.info("seed_dashboards: no users yet; deferring")
        return None

    dash = Dashboard(
        name=SEED_NAME,
        description="Default operational dashboard seeded on first boot. Edit or copy to make your own.",
        is_public=True,
        owner_id=owner.id,
        layout={},
    )
    db.add(dash)
    await db.flush()
    for w in WIDGETS:
        db.add(DashboardWidget(dashboard_id=dash.id, **w))
    await db.flush()
    logger.info("seed_dashboards: seeded '%s' (%d widgets)", dash.name, len(WIDGETS))
    return dash
