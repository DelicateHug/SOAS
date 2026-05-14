import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus, Download, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { AIActionsBar } from "@/components/ai/AIActionsBar";

interface Report {
  id: string;
  name: string;
  description: string | null;
  case_id: string | null;
  sections: Array<Record<string, unknown>>;
  is_template: boolean;
  owner_id: string;
}

export function ReportsPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftSections, setDraftSections] = useState("[]");

  const { data: reports = [] } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.get<Report[]>("/reports"),
  });

  const create = useMutation({
    mutationFn: (b: { name: string; sections: Array<Record<string, unknown>> }) =>
      api.post<Report>("/reports", b),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      setActiveId(r.id);
      setDraftName("");
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/reports/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      setActiveId(null);
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Report> }) =>
      api.patch<Report>(`/reports/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });

  const active = reports.find((r) => r.id === activeId) ?? null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <FileText size={18} /> Reports
          </h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            Multi-section report builder. Export as HTML or PDF.
          </p>
        </div>
      </div>

      <AIActionsBar pageKey="reports" context={{ active_report_id: active?.id ?? null }} />

      <Card>
        <CardBody>
          <div className="flex gap-2 mb-3">
            <input
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder="New report name"
              className="flex-1 px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            />
            <button
              onClick={() => {
                if (draftName.trim()) {
                  let sections: Array<Record<string, unknown>> = [];
                  try {
                    sections = JSON.parse(draftSections);
                  } catch {
                    /* ignore */
                  }
                  create.mutate({ name: draftName.trim(), sections });
                }
              }}
              className="inline-flex items-center gap-1 px-3 py-1 rounded text-sm bg-[var(--color-primary)] text-white"
            >
              <Plus size={12} /> Create
            </button>
          </div>
        </CardBody>
      </Card>

      <div className="grid grid-cols-12 gap-3">
        <Card className="col-span-4">
          <CardBody>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              Library ({reports.length})
            </div>
            <div className="space-y-1">
              {reports.map((r) => (
                <button
                  key={r.id}
                  onClick={() => {
                    setActiveId(r.id);
                    setDraftSections(JSON.stringify(r.sections, null, 2));
                  }}
                  className={`w-full text-left px-2 py-1.5 rounded text-sm ${
                    activeId === r.id ? "bg-[var(--color-surface-2)]" : "hover:bg-[var(--color-surface-subtle)]"
                  }`}
                >
                  <div className="truncate text-[var(--color-text)]">{r.name}</div>
                  <div className="text-[10px] text-[var(--color-text-muted)] font-mono">{r.sections.length} sections</div>
                </button>
              ))}
            </div>
          </CardBody>
        </Card>
        <Card className="col-span-8">
          <CardBody>
            {active ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <input
                    defaultValue={active.name}
                    onBlur={(e) => e.target.value !== active.name && update.mutate({ id: active.id, body: { name: e.target.value } })}
                    className="text-sm font-semibold bg-transparent border-b border-[var(--color-border)] focus:outline-none px-1"
                  />
                  <div className="flex gap-2">
                    <a href={`/api/v1/reports/${active.id}/html`} target="_blank" rel="noopener" className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]">
                      <Download size={11} /> HTML
                    </a>
                    <a href={`/api/v1/reports/${active.id}/pdf`} target="_blank" rel="noopener" className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]">
                      <Download size={11} /> PDF
                    </a>
                    <button
                      onClick={() => confirm("Delete this report?") && remove.mutate(active.id)}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
                    Sections (JSON)
                  </div>
                  <textarea
                    value={draftSections}
                    onChange={(e) => setDraftSections(e.target.value)}
                    rows={20}
                    className="w-full font-mono text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                  />
                  <button
                    onClick={() => {
                      try {
                        const sections = JSON.parse(draftSections);
                        update.mutate({ id: active.id, body: { sections } });
                      } catch (e) {
                        alert("Invalid JSON: " + String(e));
                      }
                    }}
                    className="mt-2 px-3 py-1 rounded text-sm bg-[var(--color-primary)] text-white"
                  >
                    Save sections
                  </button>
                </div>
                <div className="text-[11px] text-[var(--color-text-muted)]">
                  Each section is an object with <code>kind</code> (text / code / table), optional <code>heading</code>, and content.
                </div>
              </div>
            ) : (
              <div className="text-sm text-[var(--color-text-muted)] py-12 text-center">
                Pick a report on the left.
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
