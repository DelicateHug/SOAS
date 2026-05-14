import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Settings, Globe, Lock } from "lucide-react";
import { api } from "@/lib/api";
import type { Dashboard } from "./types";
import { WidgetRenderer } from "./WidgetRenderer";

export function DashboardDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: dash, isLoading } = useQuery({
    queryKey: ["dashboard", id],
    queryFn: () => api.get<Dashboard>(`/dashboards/${id}`),
    enabled: !!id,
  });

  if (isLoading || !dash) {
    return <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-[var(--color-text)]">{dash.name}</h1>
            {dash.is_public ? (
              <Globe size={14} className="text-[var(--color-success)]" />
            ) : (
              <Lock size={14} className="text-[var(--color-text-muted)]" />
            )}
          </div>
          {dash.description && (
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{dash.description}</p>
          )}
        </div>
        <Link
          to={`/dashboards/${dash.id}/edit`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface-2)]"
        >
          <Settings size={14} />
          Edit
        </Link>
      </div>

      {dash.widgets.length === 0 ? (
        <div className="text-sm text-[var(--color-text-muted)] py-12 text-center border border-dashed border-[var(--color-border)] rounded-md">
          No widgets yet. <Link to={`/dashboards/${dash.id}/edit`} className="text-[var(--color-primary)] hover:underline">Add some</Link>.
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-3 auto-rows-[140px]">
          {dash.widgets
            .slice()
            .sort((a, b) => a.position - b.position)
            .map((w) => (
              <div
                key={w.id}
                style={{
                  gridColumn: `span ${Math.min(12, Math.max(1, w.width))}`,
                  gridRow: `span ${Math.max(1, w.height)}`,
                }}
              >
                <WidgetRenderer widget={w} />
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
