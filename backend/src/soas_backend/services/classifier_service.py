"""Classifier: assigns an alert_category to an incident on ingest.

Walks AlertCategoryRule rows in sort_order, returns the first match.
Falls back to category key 'other' if nothing matches and that category
exists; otherwise returns None.

Rules are cached in-process for 60s — they change rarely and the
pre-processing pipeline calls this on every incoming webhook.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.alert_category import AlertCategory, AlertCategoryRule
from soas_backend.models.incident import Incident

logger = logging.getLogger(__name__)

_CACHE_TTL_S = 60.0


class _RuleCache:
    rules: list[tuple[str, AlertCategoryRule, re.Pattern[str]]] = []
    expires_at: float = 0.0


_cache = _RuleCache()


def _column_value(incident: Incident, field: str) -> str:
    """Resolve a dotted-path field reference against the incident."""
    if field == "title":
        return incident.title or ""
    if field == "summary":
        return incident.summary or ""
    if field == "source":
        return incident.source or ""
    if field == "tags":
        return " ".join(incident.tags or [])
    # Dotted-path into metadata_ or raw_event
    obj: Any = incident.metadata_ if field.startswith("metadata.") else incident.raw_event
    parts = field.split(".", 1)[1].split(".") if "." in field else []
    for p in parts:
        if not isinstance(obj, dict):
            return ""
        obj = obj.get(p)
        if obj is None:
            return ""
    if isinstance(obj, (dict, list)):
        return str(obj)
    return str(obj or "")


class ClassifierService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_rules(self) -> list[tuple[str, AlertCategoryRule, re.Pattern[str]]]:
        now = time.monotonic()
        if _cache.rules and now < _cache.expires_at:
            return _cache.rules
        result = await self.db.execute(
            select(AlertCategory)
            .options(selectinload(AlertCategory.rules))
            .order_by(AlertCategory.sort_order.asc())
        )
        compiled: list[tuple[str, AlertCategoryRule, re.Pattern[str]]] = []
        for cat in result.scalars().all():
            for rule in cat.rules:
                if not rule.is_enabled:
                    continue
                try:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    compiled.append((cat.key, rule, re.compile(rule.pattern, flags)))
                except re.error as e:
                    logger.warning("classifier: rule %s has invalid regex (%s)", rule.id, e)
        _cache.rules = compiled
        _cache.expires_at = now + _CACHE_TTL_S
        return compiled

    @classmethod
    def invalidate_cache(cls) -> None:
        _cache.rules = []
        _cache.expires_at = 0.0

    async def classify(self, incident: Incident) -> str | None:
        """Return the matching category key, or None / 'other' as fallback."""
        rules = await self._load_rules()
        for key, _rule, pattern in rules:
            value = _column_value(incident, _rule.field)
            if pattern.search(value):
                return key
        # Fallback to the 'other' bucket if it exists.
        result = await self.db.execute(
            select(AlertCategory.key).where(AlertCategory.key == "other")
        )
        return result.scalar_one_or_none()
