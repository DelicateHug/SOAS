"""Widget engine — translates widget configs into parameterized queries.

CRITICAL: every dimension, field, filter key, and bucket interval MUST
be validated against the whitelists in this module before being
interpolated into SQL. Never accept arbitrary strings from the config
into a query string. Parameter values go through SQLAlchemy bound
parameters.

Schema-driven design: the engine knows about a fixed set of "sources"
(incidents, cases, token_usage, artifact_changes, executions). Each
source declares its allowed dimensions, time column, and any joins.
Adding a new source = adding a row to SOURCES.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Source schema — whitelisted dimensions per data source.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceSchema:
    table: str
    time_column: str
    dimensions: frozenset[str]  # safe column names usable in GROUP BY / WHERE
    metric_columns: frozenset[str]  # safe column names usable as numeric aggregands


SOURCES: dict[str, SourceSchema] = {
    "incidents": SourceSchema(
        table="incidents",
        time_column="created_at",
        dimensions=frozenset({"severity", "status", "source", "team_id", "lead_id"}),
        metric_columns=frozenset(),  # incidents has no numeric metric column we aggregate
    ),
    "cases": SourceSchema(
        table="cases",
        time_column="created_at",
        dimensions=frozenset({"status", "priority", "team_id"}),
        metric_columns=frozenset(),
    ),
    "token_usage": SourceSchema(
        table="token_usage",
        time_column="created_at",
        dimensions=frozenset({"source", "caller", "model", "user_id", "target_kind"}),
        metric_columns=frozenset(
            {"input_tokens", "output_tokens", "cache_read_tokens", "cache_create_tokens", "cost_usd"}
        ),
    ),
    "artifact_changes": SourceSchema(
        table="artifact_changes",
        time_column="created_at",
        dimensions=frozenset({"kind", "action", "actor_id"}),
        metric_columns=frozenset(),
    ),
    "executions": SourceSchema(
        table="execution_logs",
        time_column="started_at",
        dimensions=frozenset({"status", "automation_id", "triggered_by"}),
        metric_columns=frozenset(),
    ),
}


BUCKET_TRUNC: dict[str, str] = {
    "hour": "hour",
    "day": "day",
    "week": "week",
    "month": "month",
}


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def _safe_dim(schema: SourceSchema, dim: str) -> str:
    if dim not in schema.dimensions:
        raise ValueError(f"Dimension '{dim}' not allowed on source '{schema.table}'")
    return dim


def _safe_metric(schema: SourceSchema, metric: str) -> str:
    if metric not in schema.metric_columns:
        raise ValueError(f"Metric '{metric}' not allowed on source '{schema.table}'")
    return metric


def _resolve_since(time_range: str | None) -> datetime:
    """Parse 'last_24h', 'last_7d', 'last_30d', 'last_90d' or default to last 30d."""
    now = datetime.now(timezone.utc)
    if time_range == "last_24h":
        return now - timedelta(hours=24)
    if time_range == "last_7d":
        return now - timedelta(days=7)
    if time_range == "last_90d":
        return now - timedelta(days=90)
    return now - timedelta(days=30)


def _apply_filters(
    schema: SourceSchema,
    filters: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Build WHERE clause fragments from a {dimension: value} dict.

    Only whitelisted dimensions are honoured. Values are parameterised.
    """
    if not filters:
        return "", {}
    fragments: list[str] = []
    params: dict[str, Any] = {}
    for i, (key, value) in enumerate(filters.items()):
        if key not in schema.dimensions:
            continue  # silently drop invalid filter keys
        pname = f"f_{i}"
        fragments.append(f'"{key}" = :{pname}')
        params[pname] = value
    if not fragments:
        return "", {}
    return " AND " + " AND ".join(fragments), params


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

WidgetResult = dict[str, Any]


class WidgetEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, widget_type: str, config: dict[str, Any]) -> WidgetResult:
        """Dispatch to the right SQL builder. Returns {data: [...], meta: {...}}."""
        builders: dict[str, Any] = {
            "counter": self._counter,
            "top_n": self._top_n,
            "timeseries": self._timeseries,
            "pie": self._pie,
            "stacked_bar": self._stacked_bar,
            "table": self._table,
            "duration_stat": self._duration_stat,
            "ratio": self._ratio,
            # Token-usage specialised wrappers
            "tokens_counter": lambda c: self._counter({**c, "source": "token_usage"}),
            "tokens_top_n": lambda c: self._top_n({**c, "source": "token_usage"}),
            "tokens_timeseries": lambda c: self._timeseries({**c, "source": "token_usage"}),
            "tokens_pie": lambda c: self._pie({**c, "source": "token_usage"}),
            "tokens_table": lambda c: self._table({**c, "source": "token_usage"}),
            # Artifact-change widgets
            "changes_counter": lambda c: self._counter({**c, "source": "artifact_changes"}),
            "changes_top_n": lambda c: self._top_n({**c, "source": "artifact_changes"}),
            "changes_timeseries": lambda c: self._timeseries({**c, "source": "artifact_changes"}),
            "changes_pie": lambda c: self._pie({**c, "source": "artifact_changes"}),
            "changes_table": lambda c: self._table({**c, "source": "artifact_changes"}),
        }
        builder = builders.get(widget_type)
        if builder is None:
            raise ValueError(f"Unknown widget_type: {widget_type}")
        return await builder(config)

    # -----------------------------------------------------------------------
    # Builders
    # -----------------------------------------------------------------------

    async def _counter(self, config: dict[str, Any]) -> WidgetResult:
        schema = SOURCES[config.get("source", "incidents")]
        since = _resolve_since(config.get("time_range"))
        filter_sql, filter_params = _apply_filters(schema, config.get("filters"))

        metric = config.get("metric")  # None → COUNT(*); else SUM("metric")
        if metric:
            expr = f'COALESCE(SUM("{_safe_metric(schema, metric)}"), 0)'
        else:
            expr = "COUNT(*)"

        sql = f"""
            SELECT {expr} AS value
            FROM {schema.table}
            WHERE "{schema.time_column}" >= :since {filter_sql}
        """
        result = await self.db.execute(text(sql), {"since": since, **filter_params})
        value = result.scalar_one()
        return {"data": {"value": float(value or 0)}, "meta": {"since": since.isoformat()}}

    async def _top_n(self, config: dict[str, Any]) -> WidgetResult:
        schema = SOURCES[config.get("source", "incidents")]
        since = _resolve_since(config.get("time_range"))
        dim = _safe_dim(schema, config["dimension"])
        limit = min(int(config.get("limit", 10)), 100)
        filter_sql, filter_params = _apply_filters(schema, config.get("filters"))

        metric = config.get("metric")
        if metric:
            expr = f'COALESCE(SUM("{_safe_metric(schema, metric)}"), 0)'
        else:
            expr = "COUNT(*)"

        sql = f"""
            SELECT "{dim}" AS bucket, {expr} AS value
            FROM {schema.table}
            WHERE "{schema.time_column}" >= :since {filter_sql}
            GROUP BY "{dim}"
            ORDER BY value DESC
            LIMIT :limit
        """
        result = await self.db.execute(
            text(sql), {"since": since, "limit": limit, **filter_params}
        )
        rows = [
            {"bucket": str(r.bucket) if r.bucket is not None else "(none)", "value": float(r.value or 0)}
            for r in result.all()
        ]
        return {"data": rows, "meta": {"since": since.isoformat(), "limit": limit}}

    async def _timeseries(self, config: dict[str, Any]) -> WidgetResult:
        schema = SOURCES[config.get("source", "incidents")]
        since = _resolve_since(config.get("time_range"))
        bucket = config.get("bucket", "day")
        if bucket not in BUCKET_TRUNC:
            raise ValueError(f"Unknown bucket: {bucket}")
        filter_sql, filter_params = _apply_filters(schema, config.get("filters"))

        metric = config.get("metric")
        expr = (
            f'COALESCE(SUM("{_safe_metric(schema, metric)}"), 0)'
            if metric else "COUNT(*)"
        )

        split_by_dim = config.get("split_by")
        if split_by_dim:
            split_col = _safe_dim(schema, split_by_dim)
            sql = f"""
                SELECT
                    DATE_TRUNC(:bucket, "{schema.time_column}") AS ts,
                    "{split_col}" AS series,
                    {expr} AS value
                FROM {schema.table}
                WHERE "{schema.time_column}" >= :since {filter_sql}
                GROUP BY ts, series
                ORDER BY ts ASC, series ASC
            """
        else:
            sql = f"""
                SELECT
                    DATE_TRUNC(:bucket, "{schema.time_column}") AS ts,
                    {expr} AS value
                FROM {schema.table}
                WHERE "{schema.time_column}" >= :since {filter_sql}
                GROUP BY ts
                ORDER BY ts ASC
            """
        result = await self.db.execute(
            text(sql), {"since": since, "bucket": bucket, **filter_params}
        )
        rows: list[dict[str, Any]] = []
        for r in result.all():
            row: dict[str, Any] = {"ts": r.ts.isoformat() if r.ts else None, "value": float(r.value or 0)}
            if split_by_dim:
                row["series"] = str(getattr(r, "series", None) or "(none)")
            rows.append(row)
        return {
            "data": rows,
            "meta": {"since": since.isoformat(), "bucket": bucket, "split_by": split_by_dim},
        }

    async def _pie(self, config: dict[str, Any]) -> WidgetResult:
        # Pie is top_n without a numeric limit cap; everything else can lump as "Other".
        return await self._top_n({**config, "limit": int(config.get("limit", 8))})

    async def _stacked_bar(self, config: dict[str, Any]) -> WidgetResult:
        # Stacked bar is timeseries with a split_by dimension and bucket="day"|"week".
        return await self._timeseries({**config, "bucket": config.get("bucket", "day")})

    async def _table(self, config: dict[str, Any]) -> WidgetResult:
        schema = SOURCES[config.get("source", "incidents")]
        since = _resolve_since(config.get("time_range"))
        filter_sql, filter_params = _apply_filters(schema, config.get("filters"))
        columns: list[str] = config.get("columns") or list(schema.dimensions)[:5]
        safe_cols = [c for c in columns if c in schema.dimensions or c in schema.metric_columns or c == schema.time_column]
        if not safe_cols:
            return {"data": [], "meta": {"since": since.isoformat()}}
        cols_sql = ", ".join(f'"{c}"' for c in safe_cols)
        limit = min(int(config.get("limit", 50)), 500)
        sql = f"""
            SELECT {cols_sql}
            FROM {schema.table}
            WHERE "{schema.time_column}" >= :since {filter_sql}
            ORDER BY "{schema.time_column}" DESC
            LIMIT :limit
        """
        result = await self.db.execute(
            text(sql), {"since": since, "limit": limit, **filter_params}
        )
        rows = [
            {c: _serialise(getattr(r, c)) for c in safe_cols} for r in result.all()
        ]
        return {"data": rows, "meta": {"since": since.isoformat(), "columns": safe_cols}}

    async def _duration_stat(self, config: dict[str, Any]) -> WidgetResult:
        """Compute a duration aggregate (mean/median/p95/max) between two columns."""
        schema = SOURCES[config.get("source", "incidents")]
        since = _resolve_since(config.get("time_range"))
        start_col = config.get("start_column", "created_at")
        end_col = config.get("end_column", "resolved_at")
        # Whitelist both column refs.
        for col in (start_col, end_col):
            if col != schema.time_column and col not in schema.dimensions and col not in {"resolved_at", "closed_at"}:
                raise ValueError(f"Column '{col}' not allowed for duration_stat on {schema.table}")
        stat: Literal["mean", "median", "p95", "max"] = config.get("stat", "mean")
        stat_expr = {
            "mean": 'AVG(EXTRACT(EPOCH FROM ("end" - "start")))',
            "median": 'PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM ("end" - "start")))',
            "p95": 'PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM ("end" - "start")))',
            "max": 'MAX(EXTRACT(EPOCH FROM ("end" - "start")))',
        }[stat]
        sql = f"""
            SELECT {stat_expr} AS seconds
            FROM (
                SELECT "{start_col}" AS "start", "{end_col}" AS "end"
                FROM {schema.table}
                WHERE "{schema.time_column}" >= :since
                  AND "{end_col}" IS NOT NULL
            ) sub
        """
        result = await self.db.execute(text(sql), {"since": since})
        value = result.scalar_one_or_none() or 0
        return {"data": {"seconds": float(value)}, "meta": {"stat": stat, "since": since.isoformat()}}

    async def _ratio(self, config: dict[str, Any]) -> WidgetResult:
        schema = SOURCES[config.get("source", "incidents")]
        since = _resolve_since(config.get("time_range"))
        # numerator and denominator each have their own filter set
        num_filter_sql, num_params = _apply_filters(schema, config.get("numerator_filters"))
        den_filter_sql, den_params = _apply_filters(schema, config.get("denominator_filters"))
        # Rename so they don't collide
        num_params = {f"n_{k}": v for k, v in num_params.items()}
        den_params = {f"d_{k}": v for k, v in den_params.items()}
        num_filter_sql = num_filter_sql.replace(":f_", ":n_f_")
        den_filter_sql = den_filter_sql.replace(":f_", ":d_f_")

        sql = f"""
            SELECT
                (SELECT COUNT(*) FROM {schema.table}
                 WHERE "{schema.time_column}" >= :since {num_filter_sql}) AS numerator,
                (SELECT COUNT(*) FROM {schema.table}
                 WHERE "{schema.time_column}" >= :since {den_filter_sql}) AS denominator
        """
        result = await self.db.execute(text(sql), {"since": since, **num_params, **den_params})
        row = result.one()
        n = float(row.numerator or 0)
        d = float(row.denominator or 0)
        ratio = (n / d) if d > 0 else 0.0
        return {
            "data": {"numerator": n, "denominator": d, "ratio": ratio},
            "meta": {"since": since.isoformat()},
        }


def _serialise(v: Any) -> Any:
    """Make SQLAlchemy row values JSON-safe."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "hex"):  # UUID
        return str(v)
    try:
        return float(v) if isinstance(v, (int, float)) else str(v)
    except Exception:
        return str(v)
