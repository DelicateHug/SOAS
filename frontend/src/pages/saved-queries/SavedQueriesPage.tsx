import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Star, Trash2, Play, Globe, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { AIActionsBar } from "@/components/ai/AIActionsBar";

interface SavedQuery {
  id: string;
  name: string;
  description: string | null;
  query_type: string;
  query_text: string;
  is_public: boolean;
  tags: string[];
  owner_id: string;
  favorite_count: number;
  is_favorite: boolean;
}

const QUERY_TYPES = [
  { value: "incidents_sql", label: "Incidents (SQL)" },
  { value: "raw_sql", label: "Raw SQL (admin)" },
  { value: "leql", label: "LEQL (connector)" },
  { value: "kql", label: "KQL (connector)" },
];

export function SavedQueriesPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);
  const [paramsJson, setParamsJson] = useState("{}");
  const [running, setRunning] = useState(false);
  const [showNew, setShowNew] = useState(false);

  const { data: queries = [], isLoading } = useQuery({
    queryKey: ["saved-queries"],
    queryFn: () => api.get<SavedQuery[]>("/saved-queries"),
  });

  const create = useMutation({
    mutationFn: (body: Partial<SavedQuery>) => api.post<SavedQuery>("/saved-queries", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["saved-queries"] });
      setShowNew(false);
    },
  });
  const toggleFav = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) =>
      on ? api.post(`/saved-queries/${id}/favorite`) : api.delete(`/saved-queries/${id}/favorite`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-queries"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/saved-queries/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["saved-queries"] }),
  });

  const active = queries.find((q) => q.id === activeId) ?? null;

  async function run() {
    if (!active) return;
    setRunning(true);
    setResult(null);
    try {
      const params = JSON.parse(paramsJson || "{}");
      const r = await api.post(`/saved-queries/${active.id}/execute`, { parameters: params });
      setResult(r);
    } catch (e) {
      setResult({ error: String(e) });
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Saved Queries</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            Reusable hunting queries with ${"{"}case_id{"}"} / ${"{"}hostname{"}"} templating.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
        >
          <Plus size={14} />
          New query
        </button>
      </div>

      <AIActionsBar pageKey="saved_queries" context={{}} />

      {showNew && <NewQueryForm onSubmit={(b) => create.mutate(b)} onCancel={() => setShowNew(false)} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card className="lg:col-span-1">
          <CardBody>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              Library {isLoading && "(loading…)"}
            </div>
            <div className="space-y-1">
              {queries.map((q) => (
                <div
                  key={q.id}
                  className={`px-2 py-1.5 rounded cursor-pointer flex items-center justify-between gap-2 ${
                    activeId === q.id ? "bg-[var(--color-surface-2)]" : "hover:bg-[var(--color-surface-subtle)]"
                  }`}
                  onClick={() => setActiveId(q.id)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-[var(--color-text)] truncate">{q.name}</div>
                    <div className="text-[10px] text-[var(--color-text-muted)] font-mono">{q.query_type}</div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleFav.mutate({ id: q.id, on: !q.is_favorite });
                    }}
                  >
                    <Star
                      size={12}
                      fill={q.is_favorite ? "var(--color-warning)" : "none"}
                      className={q.is_favorite ? "text-[var(--color-warning)]" : "text-[var(--color-text-muted)]"}
                    />
                  </button>
                  {q.is_public ? (
                    <Globe size={11} className="text-[var(--color-success)]" />
                  ) : (
                    <Lock size={11} className="text-[var(--color-text-muted)]" />
                  )}
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardBody>
            {active ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold">{active.name}</div>
                    <div className="text-xs text-[var(--color-text-muted)]">{active.description}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={run}
                      disabled={running}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
                    >
                      <Play size={11} /> {running ? "Running…" : "Run"}
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`Delete "${active.name}"?`)) {
                          remove.mutate(active.id);
                          setActiveId(null);
                        }
                      }}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
                <pre className="text-xs bg-[var(--color-surface-2)] p-3 rounded font-mono overflow-auto whitespace-pre-wrap">
                  {active.query_text}
                </pre>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
                    Parameters (JSON)
                  </div>
                  <textarea
                    value={paramsJson}
                    onChange={(e) => setParamsJson(e.target.value)}
                    rows={3}
                    className="w-full font-mono text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                  />
                </div>
                {result !== null && (
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
                      Result
                    </div>
                    <pre className="text-xs bg-[var(--color-surface-2)] p-3 rounded font-mono overflow-auto max-h-96">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-sm text-[var(--color-text-muted)] py-12 text-center">
                Pick a query from the library to inspect or run.
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function NewQueryForm({ onSubmit, onCancel }: { onSubmit: (b: Partial<SavedQuery>) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [queryType, setQueryType] = useState("incidents_sql");
  const [queryText, setQueryText] = useState("SELECT id, title, severity FROM incidents WHERE created_at >= NOW() - INTERVAL '7 days' LIMIT 50");
  const [isPublic, setIsPublic] = useState(false);

  return (
    <Card>
      <CardBody>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Query name"
            className="px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            autoFocus
          />
          <select
            value={queryType}
            onChange={(e) => setQueryType(e.target.value)}
            className="px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
          >
            {QUERY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <textarea
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          rows={6}
          className="w-full font-mono text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
        />
        <div className="flex items-center justify-between mt-2">
          <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
            <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} />
            Public
          </label>
          <div className="flex gap-2">
            <button onClick={onCancel} className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)]">
              Cancel
            </button>
            <button
              onClick={() => {
                if (!name.trim() || !queryText.trim()) return;
                onSubmit({ name, query_type: queryType, query_text: queryText, is_public: isPublic });
              }}
              className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-white"
            >
              Create
            </button>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
