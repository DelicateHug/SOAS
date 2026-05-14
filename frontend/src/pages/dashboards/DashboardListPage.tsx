import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, LayoutDashboard, Trash2, Globe, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import type { Dashboard, DashboardCreate } from "./types";

export function DashboardListPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIsPublic, setNewIsPublic] = useState(false);

  const { data: dashboards = [], isLoading } = useQuery({
    queryKey: ["dashboards"],
    queryFn: () => api.get<Dashboard[]>("/dashboards"),
  });

  const create = useMutation({
    mutationFn: (body: DashboardCreate) => api.post<Dashboard>("/dashboards", body),
    onSuccess: (dash) => {
      qc.invalidateQueries({ queryKey: ["dashboards"] });
      navigate(`/dashboards/${dash.id}/edit`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/dashboards/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dashboards"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text)]">Dashboards</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            Build custom dashboards from widgets over incidents, cases, token usage, and audit data.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
        >
          <Plus size={14} />
          New dashboard
        </button>
      </div>

      {showNew && (
        <Card>
          <CardBody>
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <label className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] block mb-1">
                  Name
                </label>
                <input
                  className="w-full px-3 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] text-[var(--color-text)]"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoFocus
                />
              </div>
              <label className="inline-flex items-center gap-2 text-sm text-[var(--color-text-muted)]">
                <input
                  type="checkbox"
                  checked={newIsPublic}
                  onChange={(e) => setNewIsPublic(e.target.checked)}
                />
                Public
              </label>
              <button
                onClick={() => {
                  if (!newName.trim()) return;
                  create.mutate({ name: newName.trim(), is_public: newIsPublic });
                }}
                disabled={create.isPending || !newName.trim()}
                className="px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
              >
                Create
              </button>
              <button
                onClick={() => {
                  setShowNew(false);
                  setNewName("");
                  setNewIsPublic(false);
                }}
                className="px-3 py-1.5 rounded text-sm border border-[var(--color-border)] text-[var(--color-text)]"
              >
                Cancel
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>
      ) : dashboards.length === 0 ? (
        <Card>
          <CardBody className="py-12 text-center">
            <LayoutDashboard className="mx-auto text-[var(--color-text-muted)] mb-2" size={32} />
            <p className="text-sm text-[var(--color-text-muted)]">
              No dashboards yet. Create one to get started.
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {dashboards.map((d) => (
            <Card key={d.id} className="hover:border-[var(--color-primary)] transition-colors">
              <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <Link
                    to={`/dashboards/${d.id}`}
                    className="flex-1 min-w-0 text-[var(--color-text)] hover:text-[var(--color-primary)]"
                  >
                    <div className="text-sm font-semibold truncate">{d.name}</div>
                    {d.description && (
                      <div className="text-xs text-[var(--color-text-muted)] mt-1 line-clamp-2">
                        {d.description}
                      </div>
                    )}
                  </Link>
                  <div className="flex items-center gap-1 shrink-0">
                    {d.is_public ? (
                      <Globe size={12} className="text-[var(--color-success)]" />
                    ) : (
                      <Lock size={12} className="text-[var(--color-text-muted)]" />
                    )}
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--color-text-muted)]">
                  <Link to={`/dashboards/${d.id}/edit`} className="hover:text-[var(--color-primary)]">
                    Edit
                  </Link>
                  <button
                    onClick={() => {
                      if (confirm(`Delete dashboard "${d.name}"?`)) {
                        remove.mutate(d.id);
                      }
                    }}
                    className="inline-flex items-center gap-1 hover:text-[var(--color-danger)]"
                  >
                    <Trash2 size={11} />
                    Delete
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
