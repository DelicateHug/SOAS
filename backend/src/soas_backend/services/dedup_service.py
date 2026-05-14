"""Entity duplicate-detection. Within a 12-hour rolling window, link
new incidents to an existing parent when their entity tuple matches.

The entity tuple is pulled from Incident.metadata_ keys:
  hostname, username, src_ip, file_hash, alert_type

If at least one of those keys matches the same key on a recent
incident — AND the categories match (or both are uncategorised) — we
link via parent_incident_id pointing at the *root* of the cluster
(never a grandchild).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.incident import Incident

logger = logging.getLogger(__name__)

CLUSTER_WINDOW = timedelta(hours=12)
ENTITY_KEYS = ("hostname", "username", "src_ip", "file_hash", "alert_type")


def _extract_entities(incident: Incident) -> dict[str, str]:
    out: dict[str, str] = {}
    meta = incident.metadata_ or {}
    for k in ENTITY_KEYS:
        v = meta.get(k)
        if isinstance(v, str) and v:
            out[k] = v
    return out


class DedupService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_parent(self, incident: Incident) -> Incident | None:
        """Locate an existing incident this one should be linked under.

        Returns the *root* of the matching cluster (the incident with no
        parent_incident_id), or None if no match.
        """
        entities = _extract_entities(incident)
        if not entities:
            return None

        since = datetime.now(timezone.utc) - CLUSTER_WINDOW
        # Pull candidate incidents in window — narrow with category match if set.
        q = (
            select(Incident)
            .where(Incident.created_at >= since)
            .where(Incident.id != incident.id)
            .order_by(Incident.created_at.asc())
        )
        if incident.category_key:
            q = q.where(
                or_(
                    Incident.category_key == incident.category_key,
                    Incident.category_key.is_(None),
                )
            )
        # Limit to a sane window of recent rows; entity match is a python step.
        q = q.limit(500)

        result = await self.db.execute(q)
        candidates = list(result.scalars().all())

        for cand in candidates:
            cand_entities = _extract_entities(cand)
            if not cand_entities:
                continue
            # Match on any shared, equal key
            shared = set(entities) & set(cand_entities)
            if not any(entities[k] == cand_entities[k] for k in shared):
                continue
            # Walk up to the root
            root = cand
            seen: set[UUID] = set()
            while root.parent_incident_id is not None and root.parent_incident_id not in seen:
                seen.add(root.id)
                r = await self.db.execute(
                    select(Incident).where(Incident.id == root.parent_incident_id)
                )
                parent = r.scalar_one_or_none()
                if parent is None:
                    break
                root = parent
            return root
        return None

    async def link_to_parent(self, child: Incident, parent: Incident) -> None:
        child.parent_incident_id = parent.id
        await self.db.flush()
