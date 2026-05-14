import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import type { DashboardWidgetData, WidgetCreate, WidgetResult } from "./types";

const PIE_COLORS = [
  "#0b63ce", "#00c389", "#f59f00", "#d6324a", "#7c3aed",
  "#0891b2", "#84cc16", "#ec4899", "#64748b",
];

interface Props {
  widget: DashboardWidgetData;
  /** When live=true, re-execute via render-widget endpoint (for editor preview). */
  live?: boolean;
}

export function WidgetRenderer({ widget, live = false }: Props) {
  const [result, setResult] = useState<WidgetResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const fetcher = live
      ? api.post<WidgetResult>("/dashboards/render-widget", {
          title: widget.title,
          widget_type: widget.widget_type,
          config: widget.config,
        } as WidgetCreate)
      : api.get<WidgetResult>(`/dashboards/widgets/${widget.id}/data`);
    fetcher
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [widget.id, widget.widget_type, JSON.stringify(widget.config), live]);

  return (
    <Card className="h-full flex flex-col">
      <div className="px-4 py-2.5 border-b border-[var(--color-border)] flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">{widget.title}</h3>
      </div>
      <CardBody className="flex-1 min-h-0 overflow-auto">
        {loading && (
          <div className="text-xs text-[var(--color-text-muted)] py-6 text-center">Loading…</div>
        )}
        {error && (
          <div className="text-xs text-[var(--color-danger)] py-6 text-center font-mono">{error}</div>
        )}
        {!loading && !error && result && <RenderBody widget={widget} result={result} />}
      </CardBody>
    </Card>
  );
}

function RenderBody({ widget, result }: { widget: DashboardWidgetData; result: WidgetResult }) {
  const t = widget.widget_type;
  if (t === "counter" || t === "tokens_counter" || t === "changes_counter") {
    const value = (result.data as { value: number }).value;
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <div className="text-4xl font-bold text-[var(--color-text)] font-mono">
          {Number.isFinite(value) ? value.toLocaleString() : "—"}
        </div>
      </div>
    );
  }

  if (t === "ratio") {
    const d = result.data as { numerator: number; denominator: number; ratio: number };
    return (
      <div className="flex flex-col items-center justify-center h-full gap-1">
        <div className="text-3xl font-bold text-[var(--color-text)] font-mono">
          {(d.ratio * 100).toFixed(1)}%
        </div>
        <div className="text-xs text-[var(--color-text-muted)] font-mono">
          {d.numerator.toLocaleString()} / {d.denominator.toLocaleString()}
        </div>
      </div>
    );
  }

  if (t === "duration_stat") {
    const seconds = (result.data as { seconds: number }).seconds;
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <div className="text-3xl font-bold text-[var(--color-text)] font-mono">
          {formatDuration(seconds)}
        </div>
      </div>
    );
  }

  if (t === "top_n" || t === "tokens_top_n" || t === "changes_top_n") {
    const rows = result.data as { bucket: string; value: number }[];
    return (
      <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 28)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 80, right: 16, top: 8, bottom: 8 }}>
          <XAxis type="number" stroke="var(--color-text-muted)" fontSize={11} />
          <YAxis dataKey="bucket" type="category" stroke="var(--color-text-muted)" fontSize={11} width={70} />
          <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", fontSize: 12 }} />
          <Bar dataKey="value" fill="var(--color-primary)" />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (t === "pie") {
    const rows = result.data as { bucket: string; value: number }[];
    return (
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="bucket" cx="50%" cy="50%" outerRadius={80} label fontSize={11}>
            {rows.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (t === "timeseries" || t === "tokens_timeseries" || t === "changes_timeseries" || t === "stacked_bar") {
    const rows = result.data as { ts: string; value: number; series?: string }[];
    const hasSeries = rows.some((r) => r.series !== undefined);
    if (!hasSeries) {
      return (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={rows} margin={{ left: 16, right: 16, top: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="ts" stroke="var(--color-text-muted)" fontSize={11} tickFormatter={(v) => v.slice(5, 10)} />
            <YAxis stroke="var(--color-text-muted)" fontSize={11} />
            <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", fontSize: 12 }} />
            <Line type="monotone" dataKey="value" stroke="var(--color-primary)" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      );
    }
    // Stacked / split: pivot rows by series
    const tsKeys = Array.from(new Set(rows.map((r) => r.ts)));
    const seriesKeys = Array.from(new Set(rows.map((r) => r.series ?? "(none)")));
    const pivoted = tsKeys.map((ts) => {
      const out: Record<string, string | number> = { ts };
      for (const s of seriesKeys) {
        const match = rows.find((r) => r.ts === ts && (r.series ?? "(none)") === s);
        out[s] = match?.value ?? 0;
      }
      return out;
    });
    return (
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={pivoted} margin={{ left: 16, right: 16, top: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="ts" stroke="var(--color-text-muted)" fontSize={11} tickFormatter={(v: string) => v.slice(5, 10)} />
          <YAxis stroke="var(--color-text-muted)" fontSize={11} />
          <Tooltip contentStyle={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {seriesKeys.map((s, i) => (
            <Bar key={s} dataKey={s} stackId="a" fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (t === "table" || t === "tokens_table" || t === "changes_table") {
    const rows = result.data as Record<string, unknown>[];
    if (!rows.length) {
      return <div className="text-xs text-[var(--color-text-muted)] py-6 text-center">No rows.</div>;
    }
    const cols = Object.keys(rows[0] ?? {});
    return (
      <div className="overflow-auto">
        <table className="w-full text-[12px] border-separate border-spacing-0">
          <thead>
            <tr>
              {cols.map((c) => (
                <th
                  key={c}
                  className="px-2 py-1.5 text-left text-[10.5px] uppercase tracking-wide font-semibold text-[var(--color-text-muted)] bg-[var(--color-surface-2)] border-b border-[var(--color-border)]"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="hover:bg-[var(--color-surface-subtle)]">
                {cols.map((c) => (
                  <td key={c} className="px-2 py-1.5 border-b border-[var(--color-border)] font-mono text-[11.5px] text-[var(--color-text)]">
                    {formatCell(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return <pre className="text-xs">{JSON.stringify(result.data, null, 2)}</pre>;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
