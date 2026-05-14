import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { Plus, Trash2, Edit2, Eye, EyeOff, X, Share2 } from "lucide-react";

interface UserSecret {
  id: string;
  name: string;
  description: string | null;
  sensitive: boolean;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

interface Role {
  id: string;
  name: string;
  display_name: string;
}

interface SharePermission {
  role_id: string;
  role_name: string | null;
  can_read: boolean;
}

interface UserSecretWithValue extends UserSecret {
  value: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number; page: number; per_page: number; total_pages: number };
}

export function UserSecretsPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingSecret, setEditingSecret] = useState<UserSecret | null>(null);
  const [revealedId, setRevealedId] = useState<string | null>(null);
  const [revealedValue, setRevealedValue] = useState<string | null>(null);
  const [sharingSecret, setSharingSecret] = useState<UserSecret | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formValue, setFormValue] = useState("");
  const [showFormValue, setShowFormValue] = useState(false);
  const [formSensitive, setFormSensitive] = useState(false);

  const { data: secretsResponse, isLoading } = useQuery({
    queryKey: ["user-secrets"],
    queryFn: () => api.get<PaginatedResponse<UserSecret>>("/user-secrets?per_page=100"),
  });

  const secrets = secretsResponse?.data ?? [];

  const createSecret = useToastMutation({
    mutationFn: () =>
      api.post("/user-secrets", {
        name: formName,
        description: formDescription || null,
        value: formValue,
        sensitive: formSensitive,
      }),
    loadingMessage: "Saving secret...",
    successMessage: "Secret saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-secrets"] });
      resetForm();
      setShowCreateModal(false);
    },
  });

  const updateSecret = useToastMutation({
    mutationFn: () => {
      if (!editingSecret) return Promise.reject("No secret");
      const body: Record<string, unknown> = {};
      if (formValue) body.value = formValue;
      if (formDescription !== (editingSecret.description || ""))
        body.description = formDescription || null;
      return api.patch(`/user-secrets/${editingSecret.id}`, body);
    },
    loadingMessage: "Saving secret...",
    successMessage: "Secret saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-secrets"] });
      resetForm();
      setEditingSecret(null);
    },
  });

  const deleteSecret = useToastMutation({
    mutationFn: (id: string) => api.delete(`/user-secrets/${id}`),
    loadingMessage: "Deleting secret...",
    successMessage: "Secret deleted.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["user-secrets"] }),
  });

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormValue("");
    setShowFormValue(false);
    setFormSensitive(false);
  };

  const openEdit = (s: UserSecret) => {
    setEditingSecret(s);
    setFormName(s.name);
    setFormDescription(s.description || "");
    setFormValue("");
    setShowFormValue(false);
  };

  const revealSecret = async (id: string) => {
    if (revealedId === id) {
      setRevealedId(null);
      setRevealedValue(null);
      return;
    }
    try {
      const data = await api.get<UserSecretWithValue>(`/user-secrets/${id}/value`);
      setRevealedId(id);
      setRevealedValue(data.value);
    } catch {
      // ignore
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">My Secrets</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Personal secrets accessible by automations you trigger. Only you can see the values.
          </p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Secret
        </button>
      </div>

      {isLoading ? (
        <p className="text-[var(--color-text-muted)]">Loading...</p>
      ) : secrets.length === 0 ? (
        <div className="text-center py-12 text-[var(--color-text-muted)]">
          <p>No secrets created yet.</p>
          <p className="text-sm mt-1">Add a secret to make it available in your automations.</p>
        </div>
      ) : (
        <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-surface-2)]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Description</th>
                <th className="text-left px-4 py-2 font-medium">Value</th>
                <th className="text-center px-4 py-2 font-medium">Sharing</th>
                <th className="text-left px-4 py-2 font-medium">Updated</th>
                <th className="text-right px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {secrets.map((s) => (
                <tr key={s.id} className="hover:bg-[var(--color-surface-2)]/50">
                  <td className="px-4 py-2 font-mono text-xs">{s.name}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] max-w-[200px] truncate">
                    {s.description || "-"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs max-w-[200px] truncate">
                    {s.sensitive ? (
                      <span className="text-[var(--color-text-muted)] italic">sensitive</span>
                    ) : revealedId === s.id ? (
                      revealedValue
                    ) : (
                      "***"
                    )}
                  </td>
                  <td className="px-4 py-2 text-center">
                    {s.is_shared ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400">
                        Shared
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--color-text-muted)]">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--color-text-muted)]">
                    {new Date(s.updated_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => setSharingSecret(s)}
                        className="p-1 rounded hover:bg-[var(--color-surface-2)] transition-colors"
                        title="Share with roles"
                      >
                        <Share2 className="w-4 h-4" />
                      </button>
                      {!s.sensitive && (
                        <button
                          onClick={() => revealSecret(s.id)}
                          className="p-1 rounded hover:bg-[var(--color-surface-2)] transition-colors"
                          title={revealedId === s.id ? "Hide value" : "Reveal value"}
                        >
                          {revealedId === s.id ? (
                            <EyeOff className="w-4 h-4" />
                          ) : (
                            <Eye className="w-4 h-4" />
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => openEdit(s)}
                        className="p-1 rounded hover:bg-[var(--color-surface-2)] transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete secret "${s.name}"?`)) {
                            deleteSecret.mutate(s.id);
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
      {(showCreateModal || editingSecret) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl w-[450px]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <h3 className="font-semibold text-sm">
                {editingSecret ? "Edit Secret" : "Create Secret"}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingSecret(null);
                  resetForm();
                }}
                className="p-1 rounded hover:bg-[var(--color-surface-2)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div>
                <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                  Name
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  disabled={!!editingSecret}
                  placeholder="e.g. my_api_key"
                  className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] disabled:opacity-50"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                  Description
                </label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="What this secret is for"
                  className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                  Value {editingSecret && (editingSecret.sensitive ? "(sensitive \u2014 enter new value to replace)" : "(leave empty to keep current)")}
                </label>
                <div className="relative">
                  <input
                    type={showFormValue ? "text" : "password"}
                    value={formValue}
                    onChange={(e) => setFormValue(e.target.value)}
                    placeholder={editingSecret ? "Enter new value..." : "Secret value"}
                    className="w-full px-3 py-2 pr-8 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowFormValue(!showFormValue)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  >
                    {showFormValue ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
              {!editingSecret && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="sensitive"
                    checked={formSensitive}
                    onChange={(e) => setFormSensitive(e.target.checked)}
                    className="rounded border-[var(--color-border)]"
                  />
                  <label htmlFor="sensitive" className="text-xs text-[var(--color-text-muted)]">
                    Sensitive (value can never be viewed after saving)
                  </label>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[var(--color-border)]">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingSecret(null);
                  resetForm();
                }}
                className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  editingSecret ? updateSecret.mutate() : createSecret.mutate()
                }
                disabled={
                  (!editingSecret && (!formName.trim() || !formValue)) ||
                  createSecret.isPending ||
                  updateSecret.isPending
                }
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50"
              >
                {editingSecret ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Share Modal */}
      {sharingSecret && (
        <ShareModal
          secret={sharingSecret}
          onClose={() => setSharingSecret(null)}
        />
      )}
    </div>
  );
}

function ShareModal({ secret, onClose }: { secret: UserSecret; onClose: () => void }) {
  const queryClient = useQueryClient();

  const { data: roles } = useQuery({
    queryKey: ["roles-list"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  const { data: currentPerms, isLoading: permsLoading } = useQuery({
    queryKey: ["secret-share-perms", secret.id],
    queryFn: () => api.get<SharePermission[]>(`/user-secrets/${secret.id}/share`),
  });

  const [selectedRoles, setSelectedRoles] = useState<Set<string>>(new Set());
  const [initialized, setInitialized] = useState(false);

  if (currentPerms && !initialized) {
    setSelectedRoles(new Set(currentPerms.map((p) => p.role_id)));
    setInitialized(true);
  }

  const shareMutation = useToastMutation({
    mutationFn: () => {
      const roleIds = Array.from(selectedRoles);
      if (roleIds.length === 0) {
        return api.delete(`/user-secrets/${secret.id}/share`);
      }
      if (secret.is_shared) {
        return api.patch(`/user-secrets/${secret.id}/share`, { role_ids: roleIds });
      }
      return api.post(`/user-secrets/${secret.id}/share`, { role_ids: roleIds });
    },
    loadingMessage: "Saving sharing settings...",
    successMessage: "Sharing settings saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-secrets"] });
      queryClient.invalidateQueries({ queryKey: ["secret-share-perms", secret.id] });
      onClose();
    },
  });

  const toggleRole = (roleId: string) => {
    setSelectedRoles((prev) => {
      const next = new Set(prev);
      if (next.has(roleId)) next.delete(roleId);
      else next.add(roleId);
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl w-[400px] max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h3 className="font-semibold text-sm">
            Share: <span className="font-mono">{secret.name}</span>
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-[var(--color-surface-2)]">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4">
          <p className="text-xs text-[var(--color-text-muted)] mb-3">
            Select roles that can access this secret via SOAS Variables. Shared secrets are accessible in automations via <code className="font-mono">get_soas_var</code>.
          </p>

          {permsLoading ? (
            <p className="text-[var(--color-text-muted)] text-sm">Loading...</p>
          ) : (
            <div className="space-y-1">
              {(roles || []).map((role) => (
                <label
                  key={role.id}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-[var(--color-surface-2)] cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedRoles.has(role.id)}
                    onChange={() => toggleRole(role.id)}
                    className="rounded"
                  />
                  <span className="text-sm">{role.display_name || role.name}</span>
                </label>
              ))}
            </div>
          )}

          {selectedRoles.size === 0 && secret.is_shared && (
            <p className="text-xs text-yellow-500 mt-2">
              No roles selected — saving will unshare this secret.
            </p>
          )}
        </div>

        <div className="flex justify-end gap-2 px-4 py-3 border-t border-[var(--color-border)]">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
          >
            Cancel
          </button>
          <button
            onClick={() => shareMutation.mutate()}
            disabled={shareMutation.isPending}
            className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50"
          >
            {shareMutation.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
