"""TokenUsage recorder + aggregations for dashboards.

Both `ai_subprocess` (CLI shell-out) and `ai_api` (Anthropic SDK) call
`record(...)`. Aggregation helpers feed dashboard widgets.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)


# Per-million-token pricing (USD). Source: Anthropic published pricing as of 2026-05.
# Kept here as a soft default; admin can override per call by passing cost_usd directly.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_million, output_per_million)
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # Aliases
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Best-effort cost estimate from the table above. Returns None for unknown models."""
    pricing = None
    key = model.lower()
    if key in MODEL_PRICING:
        pricing = MODEL_PRICING[key]
    else:
        # Fuzzy match: strip vendor prefix, version suffixes
        for k, v in MODEL_PRICING.items():
            if k in key:
                pricing = v
                break
    if pricing is None:
        return None
    in_cost = (input_tokens / 1_000_000) * pricing[0]
    out_cost = (output_tokens / 1_000_000) * pricing[1]
    return round(in_cost + out_cost, 6)


class TokenUsageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        source: str,
        caller: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_create_tokens: int = 0,
        cache_read_tokens: int = 0,
        cost_usd: float | None = None,
        user_id: UUID | None = None,
        target_id: UUID | None = None,
        target_kind: str | None = None,
        duration_ms: int | None = None,
    ) -> TokenUsage | None:
        """Append a usage row. Best-effort; never raises."""
        try:
            if cost_usd is None:
                cost_usd = estimate_cost_usd(model, input_tokens, output_tokens)
            row = TokenUsage(
                source=source,
                caller=caller,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_create_tokens=cache_create_tokens,
                cache_read_tokens=cache_read_tokens,
                cost_usd=cost_usd,
                user_id=user_id,
                target_id=target_id,
                target_kind=target_kind,
                duration_ms=duration_ms,
            )
            self.db.add(row)
            await self.db.flush()
            return row
        except Exception:
            logger.exception("token_usage.record failed source=%s caller=%s", source, caller)
            return None

    async def totals(
        self,
        *,
        since: datetime | None = None,
        caller: str | None = None,
    ) -> dict[str, Any]:
        since = since or datetime.now(timezone.utc) - timedelta(days=30)
        q = (
            select(
                func.count(TokenUsage.id).label("calls"),
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output"),
                func.coalesce(func.sum(TokenUsage.cache_create_tokens), 0).label("cache_create"),
                func.coalesce(func.sum(TokenUsage.cache_read_tokens), 0).label("cache_read"),
                func.coalesce(func.sum(TokenUsage.cost_usd), Decimal(0)).label("cost_usd"),
            )
            .where(TokenUsage.created_at >= since)
        )
        if caller:
            q = q.where(TokenUsage.caller == caller)
        row = (await self.db.execute(q)).one()
        return {
            "calls": int(row.calls),
            "input_tokens": int(row.input),
            "output_tokens": int(row.output),
            "cache_create_tokens": int(row.cache_create),
            "cache_read_tokens": int(row.cache_read),
            "cost_usd": float(row.cost_usd) if row.cost_usd is not None else 0.0,
        }
