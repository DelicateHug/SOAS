"""Daily Celery task: write SLA compliance snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from soas_workers.celery_app import app
from soas_workers.db import get_connection

logger = logging.getLogger(__name__)

VALID_END_COLUMNS = {"detected_at", "resolved_at", "closed_at"}
VALID_DIMENSIONS = {"(global)", "severity", "status", "category_key", "team_id", "source"}


@app.task(name="soas.compute_sla_snapshots")
def compute_sla_snapshots():
    """Compute and persist today's SLA snapshots for every enabled definition."""
    today = datetime.now(timezone.utc).date()
    window_start = (datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
                    - timedelta(days=30))
    window_end = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, start_column, end_column, target_seconds, dimension "
                "FROM sla_definitions WHERE is_enabled = true"
            )
            defs = cur.fetchall()

        for key, start_col, end_col, target_seconds, dimension in defs:
            if end_col not in VALID_END_COLUMNS or dimension not in VALID_DIMENSIONS:
                continue
            if start_col not in {"created_at", "detected_at"}:
                start_col = "created_at"

            if dimension == "(global)":
                group_select = "'(global)'"
                group_by = ""
            else:
                group_select = f'"{dimension}"::text'
                group_by = f'GROUP BY "{dimension}"'

            sql = f"""
                SELECT
                    {group_select} AS dim,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE EXTRACT(EPOCH FROM ("{end_col}" - "{start_col}")) <= %s
                    ) AS compliant,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY EXTRACT(EPOCH FROM ("{end_col}" - "{start_col}"))
                    ) AS p50,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (
                        ORDER BY EXTRACT(EPOCH FROM ("{end_col}" - "{start_col}"))
                    ) AS p95
                FROM incidents
                WHERE "{start_col}" >= %s
                  AND "{start_col}" <= %s
                  AND "{end_col}" IS NOT NULL
                {group_by}
            """
            with conn.cursor() as cur:
                try:
                    cur.execute(sql, (target_seconds, window_start, window_end))
                    rows = cur.fetchall()
                except Exception:
                    logger.exception("compute_sla_snapshots: query failed for key=%s", key)
                    continue
            with conn.cursor() as cur:
                for dim_value, total, compliant, p50, p95 in rows:
                    total = int(total or 0)
                    compliant = int(compliant or 0)
                    pct = (compliant / total * 100.0) if total > 0 else 0.0
                    dim_str = str(dim_value) if dim_value is not None else "(none)"
                    cur.execute(
                        """
                        INSERT INTO sla_snapshots
                          (sla_key, dim_value, captured_for, total_count, compliant_count,
                           compliance_pct, p50_seconds, p95_seconds)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sla_key, dim_value, captured_for)
                        DO UPDATE SET
                          total_count = EXCLUDED.total_count,
                          compliant_count = EXCLUDED.compliant_count,
                          compliance_pct = EXCLUDED.compliance_pct,
                          p50_seconds = EXCLUDED.p50_seconds,
                          p95_seconds = EXCLUDED.p95_seconds
                        """,
                        (key, dim_str, today, total, compliant, pct,
                         float(p50) if p50 is not None else None,
                         float(p95) if p95 is not None else None),
                    )
            conn.commit()
    logger.info("compute_sla_snapshots: wrote snapshots for %d definitions", len(defs))
    return {"definitions": len(defs)}
