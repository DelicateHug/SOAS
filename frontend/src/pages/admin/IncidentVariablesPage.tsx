import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, Trash2, Edit2, X, ToggleLeft, ToggleRight } from "lucide-react";

interface IncidentVariable {
  id: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number; page: number; per_page: number; total_pages: number };
}

export function IncidentVariablesPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingVar, setEditingVar] = useState<IncidentVariable | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formDefaultEnabled, setFormDefaultEnabled] = useState(true);

  const { data: varsResponse, isLoading } = useQuery({
    queryKey: ["incident-variables"],
    queryFn: () =>
      api.get<PaginatedResponse<IncidentVariable>>(
        "/incident-variables?per_page=100"
      ),
  });

  const variables = varsResponse?.data ?? [];

  const createVar = useMutation({
    mutationFn: () =>
      api.post("/incident-variables", {
        name: formName,
        description: formDescription || null,
        default_enabled: formDefaultEnabled,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-variables"] });
      resetForm();
      setShowCreateModal(false);
    },
  });

  const updateVar = useMutation({
    mutationFn: () => {
      if (!editingVar) return Promise.reject("No variable");
      return api.patch(`/incident-variables/${editingVar.id}`, {
        description: formDescription || null,
        default_enabled: formDefaultEnabled,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-variables"] });
      resetForm();
      setEditingVar(null);
    },
  });

  const deleteVar = useMutation({
    mutationFn: (id: string) => api.delete(`/incident-variables/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["incident-variables"] }),
  });

  const toggleDefault = useMutation({
    mutationFn: (v: IncidentVariable) =>
      api.patch(`/incident-variables/${v.id}`, {
        default_enabled: !v.default_enabled,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["incident-variables"] }),
  });

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormDefaultEnabled(true);
  };

  const openEdit = (v: IncidentVariable) => {
    setEditingVar(v);
    setFormName(v.name);
    setFormDescription(v.description || "");
    setFormDefaultEnabled(v.default_enabled);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Incident Variables</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            Define variable names for incident context. These appear as
            dropdowns on Get/Set Incident Var nodes. No values stored — just
            keys.
          </p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Create Variable
        </button>
      </div>

      {isLoading ? (
        <p className="text-[hsl(var(--muted-foreground))]">Loading...</p>
      ) : variables.length === 0 ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <p>No incident variables defined yet.</p>
          <p className="text-sm mt-1">
            Create one to enable dropdowns on incident variable nodes.
          </p>
        </div>
      ) : (
        <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[hsl(var(--accent))]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">
                  Description
                </th>
                <th className="text-center px-4 py-2 font-medium">
                  Default Enabled
                </th>
                <th className="text-right px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {variables.map((v) => (
                <tr key={v.id} className="hover:bg-[hsl(var(--accent))]/50">
                  <td className="px-4 py-2 font-mono text-xs">{v.name}</td>
                  <td className="px-4 py-2 text-[hsl(var(--muted-foreground))] max-w-[300px] truncate">
                    {v.description || "-"}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <button
                      onClick={() => toggleDefault.mutate(v)}
                      className="inline-flex items-center"
                      title={
                        v.default_enabled
                          ? "Auto-added to incidents"
                          : "Not auto-added"
                      }
                    >
                      {v.default_enabled ? (
                        <ToggleRight className="w-5 h-5 text-green-500" />
                      ) : (
                        <ToggleLeft className="w-5 h-5 text-[hsl(var(--muted-foreground))]" />
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEdit(v)}
                        className="p-1 rounded hover:bg-[hsl(var(--accent))] transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete variable "${v.name}"?`)) {
                            deleteVar.mutate(v.id);
                          }
                        }}
                        className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {(showCreateModal || editingVar) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[450px]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
              <h3 className="font-semibold text-sm">
                {editingVar ? "Edit Variable" : "Create Variable"}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingVar(null);
                  resetForm();
                }}
                className="p-1 rounded hover:bg-[hsl(var(--accent))]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Name
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  disabled={!!editingVar}
                  placeholder="e.g. source_ip, affected_user"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] disabled:opacity-50"
                />
              </div>
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Description
                </label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="What this variable represents"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formDefaultEnabled}
                  onChange={(e) => setFormDefaultEnabled(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">
                  Default enabled (auto-add to all incidents and mock incident
                  UI)
                </span>
              </label>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[hsl(var(--border))]">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingVar(null);
                  resetForm();
                }}
                className="px-3 py-1.5 text-sm rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  editingVar ? updateVar.mutate() : createVar.mutate()
                }
                disabled={
                  !formName.trim() ||
                  createVar.isPending ||
                  updateVar.isPending
                }
                className="px-3 py-1.5 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
              >
                {editingVar ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
