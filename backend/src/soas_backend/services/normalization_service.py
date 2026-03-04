"""Field normalization engine for incident payloads."""

import json
import logging
import re
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from soas_backend.models.normalization import NormalizationGroup, NormalizationRule

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes
CACHE_KEY = "normalization:global:rules"


class NormalizationService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis | None = None):
        self.db = db
        self.redis = redis

    # ------------------------------------------------------------------ #
    # CRUD methods                                                        #
    # ------------------------------------------------------------------ #

    async def list_groups(self) -> list[NormalizationGroup]:
        """Return all normalization groups ordered by display_order."""
        result = await self.db.execute(
            select(NormalizationGroup).order_by(NormalizationGroup.display_order)
        )
        return list(result.scalars().all())

    async def list_rules(self) -> list[NormalizationRule]:
        """Return all normalization rules, joined with group, ordered by
        group.display_order then rule.display_order."""
        result = await self.db.execute(
            select(NormalizationRule)
            .options(selectinload(NormalizationRule.group))
            .join(NormalizationGroup)
            .order_by(NormalizationGroup.display_order, NormalizationRule.display_order)
        )
        return list(result.scalars().all())

    async def create_rule(
        self,
        group_id: UUID,
        source_path: str,
        target_field: str,
        transform_type: str = "direct",
        transform_config: dict | None = None,
        is_required: bool = False,
        default_value: Any = None,
        display_order: int = 0,
        is_enabled: bool = True,
    ) -> NormalizationRule:
        """Create a new normalization rule and invalidate cache."""
        rule = NormalizationRule(
            group_id=group_id,
            source_path=source_path,
            target_field=target_field,
            transform_type=transform_type,
            transform_config=transform_config if transform_config is not None else {},
            is_required=is_required,
            default_value=default_value,
            display_order=display_order,
            is_enabled=is_enabled,
        )
        self.db.add(rule)
        await self.db.flush()
        await self._invalidate_cache()
        return rule

    async def update_rule(self, rule_id: UUID, **fields: Any) -> NormalizationRule:
        """Update an existing rule. Only non-None fields are applied."""
        result = await self.db.execute(
            select(NormalizationRule).where(NormalizationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise ValueError(f"Normalization rule {rule_id} not found")

        for key, value in fields.items():
            if value is not None and hasattr(rule, key):
                setattr(rule, key, value)

        await self.db.flush()
        await self._invalidate_cache()
        return rule

    async def delete_rule(self, rule_id: UUID) -> None:
        """Delete a normalization rule and invalidate cache."""
        result = await self.db.execute(
            select(NormalizationRule).where(NormalizationRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if rule is None:
            raise ValueError(f"Normalization rule {rule_id} not found")

        await self.db.delete(rule)
        await self.db.flush()
        await self._invalidate_cache()

    async def bulk_save_rules(self, rules: list[dict]) -> list[NormalizationRule]:
        """Replace ALL normalization rules with the provided list."""
        # Delete all existing rules
        await self.db.execute(delete(NormalizationRule))

        # Create new rules
        new_rules: list[NormalizationRule] = []
        for rule_data in rules:
            rule = NormalizationRule(
                group_id=rule_data["group_id"],
                source_path=rule_data["source_path"],
                target_field=rule_data["target_field"],
                transform_type=rule_data.get("transform_type", "direct"),
                transform_config=rule_data.get("transform_config", {}),
                is_required=rule_data.get("is_required", False),
                default_value=rule_data.get("default_value"),
                display_order=rule_data.get("display_order", 0),
                is_enabled=rule_data.get("is_enabled", True),
            )
            self.db.add(rule)
            new_rules.append(rule)

        await self.db.flush()
        await self._invalidate_cache()
        return new_rules

    # ------------------------------------------------------------------ #
    # Core engine                                                         #
    # ------------------------------------------------------------------ #

    async def normalize(
        self, raw_payload: dict
    ) -> tuple[dict, list[str], list[str]]:
        """Transform a raw payload into standardized incident data.

        Returns:
            A tuple of (normalized_data, errors, warnings).
        """
        rules = await self._load_rules_for_normalize()

        if not rules:
            return (
                raw_payload,
                [],
                ["No normalization rules configured; passing raw payload through"],
            )

        result: dict[str, Any] = {}
        errors: list[str] = []
        warnings: list[str] = []

        for rule in rules:
            if not rule.get("is_enabled", True):
                continue

            source_path = rule["source_path"]
            value = self._resolve_path(raw_payload, source_path)

            if value is None:
                if rule.get("is_required"):
                    errors.append(f"Required field missing: {source_path}")
                    continue
                elif rule.get("default_value") is not None:
                    value = rule["default_value"]
                else:
                    warnings.append(f"Optional field missing: {source_path}")
                    continue

            try:
                transformed = self._apply_transform(
                    value,
                    rule.get("transform_type", "direct"),
                    rule.get("transform_config", {}),
                )
            except Exception as exc:
                warnings.append(
                    f"Transform failed for {source_path} -> "
                    f"{rule['target_field']}: {exc}"
                )
                continue

            result[rule["target_field"]] = transformed

        return result, errors, warnings

    @staticmethod
    def _resolve_path(data: dict, path: str) -> Any | None:
        """Walk a dotted path (with optional array indexing) into *data*.

        Supports segments like ``alerts[0].severity`` where ``alerts[0]``
        indexes into a list.
        """
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if current is None:
                return None
            # Check for array indexing: fieldname[N]
            match = re.match(r"^(\w+)\[(\d+)\]$", part)
            if match:
                field, idx = match.group(1), int(match.group(2))
                if isinstance(current, dict) and field in current:
                    current = current[field]
                    if isinstance(current, list) and idx < len(current):
                        current = current[idx]
                    else:
                        return None
                else:
                    return None
            else:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
        return current

    @staticmethod
    def _apply_transform(value: Any, transform_type: str, config: dict) -> Any:
        """Apply a named transformation to *value*."""
        if transform_type == "direct":
            return value

        if transform_type == "regex":
            pattern = config.get("pattern", "")
            group = config.get("group", 0)
            match = re.search(pattern, str(value))
            if match:
                return match.group(group)
            return value

        if transform_type == "template":
            template = config.get("template", "{value}")
            return template.format(value=value)

        if transform_type == "static":
            return config.get("value")

        if transform_type == "lookup":
            mapping = config.get("mapping", {})
            return mapping.get(str(value), config.get("default", value))

        if transform_type == "lowercase":
            return str(value).lower()

        if transform_type == "uppercase":
            return str(value).upper()

        # Unknown transform type -- pass through
        return value

    # ------------------------------------------------------------------ #
    # Cache helpers                                                       #
    # ------------------------------------------------------------------ #

    async def _get_cached_rules(self) -> list[dict] | None:
        """Return cached rule dicts, or None on miss."""
        if self.redis is None:
            return None
        try:
            raw = await self.redis.get(CACHE_KEY)
            if raw is not None:
                return json.loads(raw)
        except Exception:
            logger.warning("Failed to read normalization cache")
        return None

    async def _cache_rules(self, rules: list[NormalizationRule]) -> None:
        """Serialize *rules* and store in Redis with TTL."""
        if self.redis is None:
            return
        try:
            payload = [
                {
                    "id": str(r.id),
                    "source_path": r.source_path,
                    "target_field": r.target_field,
                    "transform_type": r.transform_type,
                    "transform_config": r.transform_config,
                    "is_required": r.is_required,
                    "default_value": r.default_value,
                    "display_order": r.display_order,
                    "is_enabled": r.is_enabled,
                    "group_display_order": r.group.display_order
                    if r.group
                    else 0,
                }
                for r in rules
            ]
            await self.redis.set(CACHE_KEY, json.dumps(payload), ex=CACHE_TTL)
        except Exception:
            logger.warning("Failed to write normalization cache")

    async def _invalidate_cache(self) -> None:
        """Remove cached rules."""
        if self.redis is None:
            return
        try:
            await self.redis.delete(CACHE_KEY)
        except Exception:
            logger.warning("Failed to invalidate normalization cache")

    async def _load_rules_for_normalize(self) -> list[dict]:
        """Load rules for normalization, trying cache first then DB.

        Returns a list of plain dicts sorted by group display_order then
        rule display_order.
        """
        # Try cache first
        cached = await self._get_cached_rules()
        if cached is not None:
            return sorted(
                cached,
                key=lambda r: (r.get("group_display_order", 0), r.get("display_order", 0)),
            )

        # Cache miss -- query DB
        result = await self.db.execute(
            select(NormalizationRule)
            .options(selectinload(NormalizationRule.group))
            .where(NormalizationRule.is_enabled.is_(True))
            .join(NormalizationGroup)
            .order_by(
                NormalizationGroup.display_order,
                NormalizationRule.display_order,
            )
        )
        rules = list(result.scalars().all())

        # Cache for next time
        await self._cache_rules(rules)

        # Convert to dicts for the normalize engine
        return [
            {
                "id": str(r.id),
                "source_path": r.source_path,
                "target_field": r.target_field,
                "transform_type": r.transform_type,
                "transform_config": r.transform_config,
                "is_required": r.is_required,
                "default_value": r.default_value,
                "display_order": r.display_order,
                "is_enabled": r.is_enabled,
                "group_display_order": r.group.display_order if r.group else 0,
            }
            for r in rules
        ]
