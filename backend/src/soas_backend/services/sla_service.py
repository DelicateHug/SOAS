"""SLA service: definition CRUD, snapshot computation, recent reads.

Snapshots are computed against the incidents table. The dimension
declared on the SLADefinition picks the GROUP BY column; only a
small whitelist is accepted (no SQL injection risk on user input).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from soas_backend.models.sla import SLADefinition, SLASnapshot


VALID_END_COLUMNS = {"detected_at", "resolved_at", "closed_at"}
VALID_DIMENSIONS = {"(global)", "severity", "status", "category_key", "team_id", "source"}


class SLAService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_definitions(self) -> list[SLADefinition]:
        result = await self.db.execute(
            select(SLADefinition).order_by(SLADefinition.key.asc())
        )
        return list(result.scalars().all())

    async def compute_snapshot_for(self, definition: SLADefinition, day: date | None = None) -> list[SLASnapshot]:
        """Compute compliance snapshot rows for one SLA definition for `day` (default: today)."""
        if definition.end_column not in VALID_END_COLUMNS:
            return []
        if definition.dimension not in VALID_DIMENSIONS:
            return []

        day = day or datetime.now(timezone.utc).date()
        # Roll over a 30-day window for the SLA — incidents whose start_column
        # falls inside the window AND whose end_column is non-null.
        window_start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=30)
        window_end = datetime.combine(day, datetime.max.time(), tzinfo=timezone.utc)

        if definition.dimension == "(global)":
            group_select = "'(global)' AS dim"
            group_by = ""
        else:
            group_select = f'"{definition.dimension}" AS dim'
            group_by = f'GROUP BY "{definition.dimension}"'

        end_col = definition.end_column
        start_col = definition.start_column if definition.start_column in {"created_at", "detected_at"} else "created_at"

        sql = f"""
            SELECT
                {group_select},
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM ("{end_col}" - "{start_col}")) <= :target
                ) AS compliant,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM ("{end_col}" - "{start_col}"))) AS p50,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM ("{end_col}" - "{start_col}"))) AS p95
            FROM incidents
            WHERE "{start_col}" >= :ws
              AND "{start_col}" <= :we
              AND "{end_col}" IS NOT NULL
            {group_by}
        """
        result = await self.db.execute(
            text(sql),
            {"ws": window_start, "we": window_end, "target": definition.target_seconds},
        )

        snapshots: list[SLASnapshot] = []
        for row in result.all():
            total = int(row.total or 0)
            compliant = int(row.compliant or 0)
            pct = (compliant / total * 100.0) if total > 0 else 0.0
            snap = SLASnapshot(
                sla_key=definition.key,
                dim_value=str(row.dim) if row.dim is not None else "(none)",
                captured_for=day,
                total_count=total,
                compliant_count=compliant,
                compliance_pct=pct,
                p50_seconds=float(row.p50) if row.p50 is not None else None,
                p95_seconds=float(row.p95) if row.p95 is not None else None,
            )
            # Upsert: delete an existing row for the (key, dim, day) tuple, then add.
            await self.db.execute(
                text(
                    "DELETE FROM sla_snapshots "
                    "WHERE sla_key = :k AND dim_value = :d AND captured_for = :c"
                ),
                {"k": snap.sla_key, "d": snap.dim_value, "c": day},
            )
            self.db.add(snap)
            snapshots.append(snap)
        await self.db.flush()
        return snapshots

    async def compute_all(self, day: date | None = None) -> dict[str, int]:
        """Compute every enabled SLA's snapshots for `day`. Returns counts."""
        defs = await self.list_definitions()
        counts: dict[str, int] = {}
        for d in defs:
            if not d.is_enabled:
                continue
            try:
                snaps = await self.compute_snapshot_for(d, day)
                counts[d.key] = len(snaps)
            except Exception:
                counts[d.key] = 0
        return counts

    async def recent_snapshots(
        self, sla_key: str | None = None, days: int = 30
    ) -> list[SLASnapshot]:
        since = (datetime.now(timezone.utc).date() - timedelta(days=days))
        q = select(SLASnapshot).where(SLASnapshot.captured_for >= since).order_by(
            SLASnapshot.sla_key.asc(), SLASnapshot.captured_for.asc()
        )
        if sla_key:
            q = q.where(SLASnapshot.sla_key == sla_key)
        result = await self.db.execute(q)
        return list(result.scalars().all())
