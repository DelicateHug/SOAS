import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import type { Dashboard, DashboardWidgetData, WidgetCreate } from "./types";
import { SOURCES, TIME_RANGES, WIDGET_TYPES } from "./types";
import { WidgetRenderer } from "./WidgetRenderer";
import { AIActionsBar } from "@/components/ai/AIActionsBar";

export function DashboardEditPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: dash, isLoading } = useQuery({
    queryKey: ["dashboard", id],
    queryFn: () => api.get<Dashboard>(`/dashboards/${id}`),
    enabled: !!id,
  });

  const addWidget = useMutation({
    mutationFn: (body: WidgetCreate) => api.post<DashboardWidgetData>(`/dashboards/${id}/widgets`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard", id] }),
  });

  const deleteWidget = useMutation({
    mutationFn: (widgetId: string) => api.delete(`/dashboards/widgets/${widgetId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard", id] }),
  });

  const updateDash = useMutation({
    mutationFn: (body: Partial<Dashboard>) => api.patch<Dashboard>(`/dashboards/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboard", id] }),
  });

  const [editorDraft, setEditorDraft] = useState<WidgetCreate>({
    title: "",
    widget_type: "counter",
    config: { source: "incidents", time_range: "last_30d" },
    position: 0,
    width: 4,
    height: 2,
  });

  if (isLoading || !dash) {
    return <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link
            to={`/dashboards/${id}`}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-primary)]"
          >
            <ArrowLeft size={16} />
          </Link>
          <div>
            <h1 className="text-xl font-semibold text-[var(--color-text)]">Edit: {dash.name}</h1>
            <p className="text-xs text-[var(--color-text-muted)]">{dash.widgets.length} widgets</p>
          </div>
        </div>
      </div>

      <AIActionsBar
        pageKey="dashboard_edit"
        context={{ dashboard_id: dash.id, name: dash.name, widget_count: dash.widgets.length }}
      />

      {/* Dashboard meta */}
      <Card>
        <CardBody>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Field label="Name">
              <input
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={dash.name}
                onChange={(e) => updateDash.mutate({ name: e.target.value })}
              />
            </Field>
            <Field label="Description">
              <input
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={dash.description ?? ""}
                onChange={(e) => updateDash.mutate({ description: e.target.value })}
              />
            </Field>
            <Field label="Visibility">
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={dash.is_public}
                  onChange={(e) => updateDash.mutate({ is_public: e.target.checked })}
                />
                Public
              </label>
            </Field>
          </div>
        </CardBody>
      </Card>

      {/* Widget grid + add-new */}
      <div className="grid grid-cols-12 gap-3 auto-rows-[140px]">
        {dash.widgets.map((w) => (
          <div
            key={w.id}
            style={{
              gridColumn: `span ${Math.min(12, Math.max(1, w.width))}`,
              gridRow: `span ${Math.max(1, w.height)}`,
              position: "relative",
            }}
          >
            <WidgetRenderer widget={w} />
            <button
              onClick={() => {
                if (confirm(`Delete widget "${w.title}"?`)) {
                  deleteWidget.mutate(w.id);
                }
              }}
              className="absolute top-2 right-2 p-1 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-danger)] hover:border-[var(--color-danger)]"
              title="Delete widget"
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}
      </div>

      {/* Add-widget editor */}
      <Card>
        <CardBody>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-3">
            Add widget
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Title">
              <input
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={editorDraft.title}
                onChange={(e) => setEditorDraft({ ...editorDraft, title: e.target.value })}
              />
            </Field>
            <Field label="Type">
              <select
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={editorDraft.widget_type}
                onChange={(e) => setEditorDraft({ ...editorDraft, widget_type: e.target.value })}
              >
                {WIDGET_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Source">
              <select
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={(editorDraft.config.source as string) ?? "incidents"}
                onChange={(e) => setEditorDraft({
                  ...editorDraft,
                  config: { ...editorDraft.config, source: e.target.value },
                })}
              >
                {SOURCES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Time range">
              <select
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={(editorDraft.config.time_range as string) ?? "last_30d"}
                onChange={(e) => setEditorDraft({
                  ...editorDraft,
                  config: { ...editorDraft.config, time_range: e.target.value },
                })}
              >
                {TIME_RANGES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Dimension (for top_n/pie/bar)">
              <input
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
                value={(editorDraft.config.dimension as string) ?? ""}
                onChange={(e) => setEditorDraft({
                  ...editorDraft,
                  config: { ...editorDraft.config, dimension: e.target.value || undefined },
                })}
                placeholder="severity, status, caller, kind, …"
              />
            </Field>
            <Field label="Bucket (for timeseries)">
              <select
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={(editorDraft.config.bucket as string) ?? "day"}
                onChange={(e) => setEditorDraft({
                  ...editorDraft,
                  config: { ...editorDraft.config, bucket: e.target.value },
                })}
              >
                <option value="hour">Hour</option>
                <option value="day">Day</option>
                <option value="week">Week</option>
                <option value="month">Month</option>
              </select>
            </Field>
            <Field label="Width (1–12)">
              <input
                type="number"
                min={1}
                max={12}
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={editorDraft.width}
                onChange={(e) => setEditorDraft({ ...editorDraft, width: parseInt(e.target.value) || 6 })}
              />
            </Field>
            <Field label="Height (rows)">
              <input
                type="number"
                min={1}
                max={6}
                className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                value={editorDraft.height}
                onChange={(e) => setEditorDraft({ ...editorDraft, height: parseInt(e.target.value) || 2 })}
              />
            </Field>
          </div>
          <div className="mt-3 flex justify-end">
            <button
              onClick={() => {
                if (!editorDraft.title.trim()) return;
                addWidget.mutate({
                  ...editorDraft,
                  position: dash.widgets.length,
                });
                setEditorDraft({ ...editorDraft, title: "" });
              }}
              disabled={addWidget.isPending || !editorDraft.title.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
            >
              <Plus size={14} />
              Add widget
            </button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
