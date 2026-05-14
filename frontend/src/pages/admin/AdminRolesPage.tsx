import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useBranchAwareList } from "@/hooks/useBranchAwareList";
import { BranchStatusBadge, PendingCreateBadge } from "@/components/ui/BranchStatusBadge";
import { api } from "@/lib/api";
import { Plus, ChevronDown, ChevronRight } from "lucide-react";
import type { Role, Permission } from "@/types/api";
import { ProductionGuard } from "@/components/ui/ProductionGuard";

export function AdminRolesPage() {
  const queryClient = useQueryClient();
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDisplayName, setNewRoleDisplayName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");

  const { items: branchRoles, pendingCreates, isLoading } = useBranchAwareList<Role, Role[]>({
    entityType: "role",
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
    getId: (r) => r.id,
    getData: (r) => r,
  });

  const { data: allPermissions } = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api.get<Permission[]>("/roles/permissions"),
  });

  const createRole = useToastMutation({
    mutationFn: () =>
      api.post("/roles", {
        name: newRoleName,
        display_name: newRoleDisplayName,
        description: newRoleDescription || undefined,
      }),
    loadingMessage: "Creating role...",
    successMessage: "Role created.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
      setShowCreateModal(false);
      setNewRoleName("");
      setNewRoleDisplayName("");
      setNewRoleDescription("");
    },
  });

  const updatePermissions = useToastMutation({
    mutationFn: ({ roleId, permissionIds }: { roleId: string; permissionIds: string[] }) =>
      api.patch(`/roles/${roleId}`, { permission_ids: permissionIds }),
    loadingMessage: false,
    successMessage: "Permissions updated.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roles"] }),
  });

  const togglePermission = (role: Role, permission: Permission) => {
    const current = (role.permissions ?? []).map((p) => p.id);
    const updated = current.includes(permission.id)
      ? current.filter((id) => id !== permission.id)
      : [...current, permission.id];
    updatePermissions.mutate({ roleId: role.id, permissionIds: updated });
  };

  // Group permissions by resource
  const permissionsByResource = (allPermissions || []).reduce<Record<string, Permission[]>>(
    (acc, p) => {
      (acc[p.resource] ??= []).push(p);
      return acc;
    },
    {}
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Role Management</h1>
        <ProductionGuard>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90"
          >
            <Plus className="w-4 h-4" /> Create Role
          </button>
        </ProductionGuard>
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="space-y-3">
          {pendingCreates.map((cr) => (
            <div key={cr.id} className="border border-green-500/30 rounded-lg bg-green-500/5">
              <div className="w-full px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ChevronRight className="w-4 h-4 opacity-30" />
                  <div className="text-left">
                    <p className="font-medium flex items-center gap-2">
                      {(cr as unknown as { snapshot?: { display_name?: string } }).snapshot?.display_name ?? cr.title}
                      <PendingCreateBadge changeRequest={cr} />
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {branchRoles.map(({ item: role, branchStatus, changeRequest }) => (
            <div key={role.id} className={`border border-[var(--color-border)] rounded-lg ${branchStatus === "pending_delete" ? "opacity-50" : ""}`}>
              <button
                onClick={() => setExpandedRole(expandedRole === role.id ? null : role.id)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-[var(--color-surface-2)]"
              >
                <div className="flex items-center gap-3">
                  {expandedRole === role.id ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                  <div className="text-left">
                    <p className="font-medium flex items-center gap-2">
                      {role.display_name}
                      <BranchStatusBadge branchStatus={branchStatus} changeRequest={changeRequest} />
                    </p>
                    {role.description && (
                      <p className="text-xs text-[var(--color-text-muted)]">{role.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {role.is_system && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">
                      System
                    </span>
                  )}
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {(role.permissions ?? []).length} permissions
                  </span>
                </div>
              </button>

              {expandedRole === role.id && (
                <div className="border-t border-[var(--color-border)] px-4 py-4">
                  {Object.entries(permissionsByResource).map(([resource, permissions]) => (
                    <div key={resource} className="mb-3">
                      <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase mb-1">
                        {resource}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {permissions.map((perm) => {
                          const hasPermission = (role.permissions ?? []).some((rp) => rp.id === perm.id);
                          return (
                            <ProductionGuard
                              key={perm.id}
                              fallback={
                                <span
                                  className={`px-2 py-1 rounded text-xs border ${
                                    hasPermission
                                      ? "bg-[var(--color-primary)] text-[#ffffff] border-transparent"
                                      : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                                  }`}
                                >
                                  {perm.action}
                                </span>
                              }
                            >
                              <button
                                onClick={() => togglePermission(role, perm)}
                                className={`px-2 py-1 rounded text-xs border transition-colors ${
                                  hasPermission
                                    ? "bg-[var(--color-primary)] text-[#ffffff] border-transparent"
                                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-primary)]"
                                }`}
                              >
                                {perm.action}
                              </button>
                            </ProductionGuard>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create Role Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-bg)] rounded-lg p-6 w-full max-w-md border border-[var(--color-border)]">
            <h2 className="text-lg font-semibold mb-4">Create Role</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Name (slug) *</label>
                <input
                  type="text"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value.toLowerCase().replace(/\s+/g, "_"))}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
                  placeholder="custom_role"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Display Name *</label>
                <input
                  type="text"
                  value={newRoleDisplayName}
                  onChange={(e) => setNewRoleDisplayName(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
                  placeholder="Custom Role"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <input
                  type="text"
                  value={newRoleDescription}
                  onChange={(e) => setNewRoleDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
                  placeholder="Optional description"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => createRole.mutate()}
                disabled={!newRoleName || !newRoleDisplayName || createRole.isPending}
                className="px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md disabled:opacity-50"
              >
                {createRole.isPending ? "Creating..." : "Create"}
              </button>
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 border border-[var(--color-border)] rounded-md"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
