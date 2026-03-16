import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useBranchAwareList } from "@/hooks/useBranchAwareList";
import { BranchStatusBadge, PendingCreateBadge } from "@/components/ui/BranchStatusBadge";
import { api } from "@/lib/api";
import { Plus, Trash2, Edit2, Shield, Eye, EyeOff, X } from "lucide-react";
import { ProductionGuard } from "@/components/ui/ProductionGuard";

interface SOASVariable {
  id: string;
  name: string;
  description: string | null;
  value: unknown;
  is_secret: boolean;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
  source?: "soas_var" | "shared_secret";
  owner_username?: string | null;
}

interface SOASVariablePermission {
  role_id: string;
  role_name: string | null;
  can_read: boolean;
  can_write: boolean;
}

interface Role {
  id: string;
  name: string;
  display_name: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number; page: number; per_page: number; total_pages: number };
}

export function SOASVariablesPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingVar, setEditingVar] = useState<SOASVariable | null>(null);
  const [permVar, setPermVar] = useState<SOASVariable | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formValue, setFormValue] = useState("");
  const [formIsSecret, setFormIsSecret] = useState(false);

  const { items: branchItems, pendingCreates, isLoading } = useBranchAwareList<SOASVariable, PaginatedResponse<SOASVariable>>({
    entityType: "soas_variable",
    queryKey: ["soas-variables"],
    queryFn: () => api.get<PaginatedResponse<SOASVariable>>("/soas-variables?per_page=100&include_shared=true"),
    getId: (v) => v.id,
    getData: (r) => r.data,
  });

  const { data: roles } = useQuery({
    queryKey: ["roles-list"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  const createVar = useToastMutation({
    mutationFn: () => {
      let parsedValue: unknown = formValue;
      try {
        parsedValue = JSON.parse(formValue);
      } catch {
        // Keep as string
      }
      return api.post("/soas-variables", {
        name: formName,
        description: formDescription || null,
        value: parsedValue,
        is_secret: formIsSecret,
      });
    },
    loadingMessage: "Creating variable...",
    successMessage: "Variable created.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["soas-variables"] });
      resetForm();
      setShowCreateModal(false);
    },
  });

  const updateVar = useToastMutation({
    mutationFn: () => {
      if (!editingVar) return Promise.reject("No variable");
      let parsedValue: unknown = formValue;
      try {
        parsedValue = JSON.parse(formValue);
      } catch {
        // Keep as string
      }
      return api.patch(`/soas-variables/${editingVar.id}`, {
        description: formDescription || null,
        value: parsedValue,
        is_secret: formIsSecret,
      });
    },
    loadingMessage: "Updating variable...",
    successMessage: "Variable updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["soas-variables"] });
      resetForm();
      setEditingVar(null);
    },
  });

  const deleteVar = useToastMutation({
    mutationFn: (id: string) => api.delete(`/soas-variables/${id}`),
    loadingMessage: "Deleting variable...",
    successMessage: "Variable deleted.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soas-variables"] }),
  });

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormValue("");
    setFormIsSecret(false);
  };

  const openEdit = (v: SOASVariable) => {
    setEditingVar(v);
    setFormName(v.name);
    setFormDescription(v.description || "");
    setFormValue(typeof v.value === "string" ? v.value : JSON.stringify(v.value, null, 2));
    setFormIsSecret(v.is_secret);
  };

  const formatValue = (v: unknown, isSecret: boolean): string => {
    if (isSecret) return "***";
    if (v === null || v === undefined) return "null";
    if (typeof v === "string") return v;
    return JSON.stringify(v);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">SOAS Variables</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            Application-level variables accessible by automations. Permission-restricted per role.
          </p>
        </div>
        <ProductionGuard>
          <button
            onClick={() => {
              resetForm();
              setShowCreateModal(true);
            }}
            className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-colors"
          >
            <Plus className="w-4 h-4" /> Create Variable
          </button>
        </ProductionGuard>
      </div>

      {isLoading ? (
        <p className="text-[hsl(var(--muted-foreground))]">Loading...</p>
      ) : branchItems.length === 0 && pendingCreates.length === 0 ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <p>No SOAS variables created yet.</p>
          <p className="text-sm mt-1">Create one to get started.</p>
        </div>
      ) : (
        <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[hsl(var(--accent))]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Description</th>
                <th className="text-left px-4 py-2 font-medium">Value</th>
                <th className="text-center px-4 py-2 font-medium">Secret</th>
                <th className="text-right px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {pendingCreates.map((cr) => (
                <tr key={cr.id} className="bg-green-500/5">
                  <td className="px-4 py-2 font-mono text-xs">
                    <span className="flex items-center gap-1.5">
                      {(cr as unknown as { snapshot?: { name?: string } }).snapshot?.name ?? cr.title}
                      <PendingCreateBadge changeRequest={cr} />
                    </span>
                  </td>
                  <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">-</td>
                  <td className="px-4 py-2 font-mono text-xs">-</td>
                  <td className="px-4 py-2 text-center">-</td>
                  <td className="px-4 py-2 text-right text-xs text-[hsl(var(--muted-foreground))] italic">pending</td>
                </tr>
              ))}
              {branchItems.map(({ item: v, branchStatus, changeRequest }) => (
                <tr key={v.id} className={`hover:bg-[hsl(var(--accent))]/50 ${branchStatus === "pending_delete" ? "opacity-50 line-through" : ""}`}>
                  <td className="px-4 py-2 font-mono text-xs">
                    <span className="flex items-center gap-1.5">
                      {v.name}
                      {v.source === "shared_secret" && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
                          Shared
                        </span>
                      )}
                      <BranchStatusBadge branchStatus={branchStatus} changeRequest={changeRequest} />
                    </span>
                    {v.owner_username && (
                      <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                        by {v.owner_username}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-[hsl(var(--muted-foreground))] max-w-[200px] truncate">
                    {v.description || "-"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs max-w-[200px] truncate">
                    {formatValue(v.value, v.is_secret)}
                  </td>
                  <td className="px-4 py-2 text-center">
                    {v.is_secret ? (
                      <EyeOff className="w-4 h-4 text-yellow-500 inline" />
                    ) : (
                      <Eye className="w-4 h-4 text-[hsl(var(--muted-foreground))] inline" />
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {v.source === "shared_secret" ? (
                      <span className="text-xs text-[hsl(var(--muted-foreground))] italic">managed by owner</span>
                    ) : (
                      <ProductionGuard>
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setPermVar(v)}
                            className="p-1 rounded hover:bg-[hsl(var(--accent))] transition-colors"
                            title="Permissions"
                          >
                            <Shield className="w-4 h-4" />
                          </button>
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
                      </ProductionGuard>
                    )}
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
                  placeholder="e.g. api_key_virustotal"
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
                  placeholder="What this variable is for"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Value (JSON or plain string)
                </label>
                <textarea
                  value={formValue}
                  onChange={(e) => setFormValue(e.target.value)}
                  rows={3}
                  placeholder='"my_value" or {"key": "value"}'
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] font-mono"
                />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formIsSecret}
                  onChange={(e) => setFormIsSecret(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm">Secret (mask value in UI)</span>
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
                onClick={() => (editingVar ? updateVar.mutate() : createVar.mutate())}
                disabled={!formName.trim() || createVar.isPending || updateVar.isPending}
                className="px-3 py-1.5 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
              >
                {editingVar ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Permissions Modal */}
      {permVar && (
        <PermissionsModal
          variable={permVar}
          roles={roles || []}
          onClose={() => setPermVar(null)}
        />
      )}
    </div>
  );
}

function PermissionsModal({
  variable,
  roles,
  onClose,
}: {
  variable: SOASVariable;
  roles: Role[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();

  const { data: perms, isLoading } = useQuery({
    queryKey: ["soas-variable-permissions", variable.id],
    queryFn: () =>
      api.get<SOASVariablePermission[]>(`/soas-variables/${variable.id}/permissions`),
  });

  const [localPerms, setLocalPerms] = useState<Record<string, { can_read: boolean; can_write: boolean }>>({});
  const [initialized, setInitialized] = useState(false);

  if (perms && !initialized) {
    const map: Record<string, { can_read: boolean; can_write: boolean }> = {};
    for (const p of perms) {
      map[p.role_id] = { can_read: p.can_read, can_write: p.can_write };
    }
    setLocalPerms(map);
    setInitialized(true);
  }

  const saveMutation = useToastMutation({
    mutationFn: () => {
      const permissions = Object.entries(localPerms)
        .filter(([, v]) => v.can_read || v.can_write)
        .map(([role_id, v]) => ({
          role_id,
          can_read: v.can_read,
          can_write: v.can_write,
        }));
      return api.patch(`/soas-variables/${variable.id}/permissions`, { permissions });
    },
    loadingMessage: "Saving permissions...",
    successMessage: "Permissions saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["soas-variable-permissions", variable.id],
      });
      onClose();
    },
  });

  const togglePerm = (roleId: string, field: "can_read" | "can_write") => {
    setLocalPerms((prev) => {
      const current = prev[roleId] || { can_read: false, can_write: false };
      return { ...prev, [roleId]: { ...current, [field]: !current[field] } };
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[450px] max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
          <h3 className="font-semibold text-sm">
            Permissions: <span className="font-mono">{variable.name}</span>
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-[hsl(var(--accent))]">
            <X className="w-4 h-4" />
          </button>
        </div>

        {isLoading ? (
          <div className="p-4 text-[hsl(var(--muted-foreground))]">Loading...</div>
        ) : (
          <div className="p-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="pb-2 font-medium">Role</th>
                  <th className="pb-2 font-medium text-center">Read</th>
                  <th className="pb-2 font-medium text-center">Write</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[hsl(var(--border))]">
                {roles.map((role) => {
                  const p = localPerms[role.id] || { can_read: false, can_write: false };
                  return (
                    <tr key={role.id}>
                      <td className="py-2">{role.display_name || role.name}</td>
                      <td className="py-2 text-center">
                        <input
                          type="checkbox"
                          checked={p.can_read}
                          onChange={() => togglePerm(role.id, "can_read")}
                          className="rounded"
                        />
                      </td>
                      <td className="py-2 text-center">
                        <input
                          type="checkbox"
                          checked={p.can_write}
                          onChange={() => togglePerm(role.id, "can_write")}
                          className="rounded"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex justify-end gap-2 px-4 py-3 border-t border-[hsl(var(--border))]">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="px-3 py-1.5 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
          >
            Save Permissions
          </button>
        </div>
      </div>
    </div>
  );
}
