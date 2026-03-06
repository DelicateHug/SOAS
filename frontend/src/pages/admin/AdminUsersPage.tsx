import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserCheck, UserX, Shield, UserPlus, Copy, Check } from "lucide-react";
import type { PaginatedResponse, Role, ChangeRequestDetail } from "@/types/api";
import { useToast } from "@/stores/toastStore";
import { useToastMutation } from "@/hooks/useToastMutation";

interface UserRead {
  id: string;
  username: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_mfa_enabled: boolean;
  last_login_at?: string;
  roles: string[];
  created_at: string;
  updated_at: string;
}

interface AdminUserCreateResponse extends UserRead {
  temporary_password: string;
}

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [selectedUser, setSelectedUser] = useState<UserRead | null>(null);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ username: "", email: "", display_name: "" });
  const [createError, setCreateError] = useState("");
  const [createdUser, setCreatedUser] = useState<AdminUserCreateResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const { toast } = useToast();

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users", page],
    queryFn: () =>
      api.get<PaginatedResponse<UserRead>>(`/admin/users?page=${page}&per_page=25`),
  });

  const { data: roles } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  const { isDevMode } = useDeploymentMode();
  const { data: userRoleCRs } = useQuery({
    queryKey: ["change-requests", "active", "user_role"],
    queryFn: () => api.get<ChangeRequestDetail[]>("/change-requests/active?entity_type=user_role"),
    enabled: isDevMode,
    staleTime: 10_000,
  });

  // Group user_role CRs by target user_id
  const pendingRolesByUser = new Map<string, ChangeRequestDetail[]>();
  for (const cr of userRoleCRs ?? []) {
    const userId = cr.snapshot?.user_id as string | undefined;
    if (userId) {
      const list = pendingRolesByUser.get(userId) ?? [];
      list.push(cr);
      pendingRolesByUser.set(userId, list);
    }
  }

  const toggleActive = useToastMutation({
    mutationFn: (user: UserRead) =>
      user.is_active
        ? api.delete(`/admin/users/${user.id}`)
        : api.patch(`/admin/users/${user.id}`, { is_active: true }),
    successMessage: "User status updated.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const handleAssignRole = async (userId: string, roleId: string) => {
    setShowRoleModal(false);
    toast("info", "Creating change request...");
    try {
      await api.post(`/roles/users/${userId}/roles`, { role_id: roleId });
      toast("success", "Change request created. Go to Local Changes to submit for approval.");
    } catch (err: unknown) {
      const detail = (err as { detail?: string })?.detail;
      toast("error", detail || "Failed to create change request.");
    }
  };

  const removeRole = useToastMutation({
    mutationFn: ({ userId, roleId }: { userId: string; roleId: string }) =>
      api.delete(`/roles/users/${userId}/roles/${roleId}`),
    loadingMessage: "Creating change request...",
    successMessage: "Change request created. Go to Local Changes to submit it for admin approval.",
    errorMessage: (err: { detail?: string }) => err.detail || "Failed to create change request for role removal.",
  });

  const createUser = useToastMutation({
    mutationFn: (data: { username: string; email: string; display_name: string }) =>
      api.post<AdminUserCreateResponse>("/admin/users", data),
    successMessage: false,
    errorMessage: false,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      setCreatedUser(data);
      setCreateError("");
    },
    onError: (err: { detail?: string }) => {
      setCreateError(err.detail || "Failed to create user");
    },
  });

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    createUser.mutate(createForm);
  };

  const handleCloseCreateModal = () => {
    setShowCreateModal(false);
    setCreateForm({ username: "", email: "", display_name: "" });
    setCreateError("");
    setCreatedUser(null);
    setCopied(false);
  };

  const handleCopyPassword = async () => {
    if (createdUser) {
      await navigator.clipboard.writeText(createdUser.temporary_password);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">User Management</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 text-sm"
        >
          <UserPlus className="w-4 h-4" />
          Add User
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="border border-[hsl(var(--border))] rounded-lg">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[hsl(var(--border))] text-left text-sm text-[hsl(var(--muted-foreground))]">
                <th className="px-4 py-3 font-medium">User</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Roles</th>
                <th className="px-4 py-3 font-medium">MFA</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last Login</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {users?.data.map((user) => (
                <tr key={user.id} className="hover:bg-[hsl(var(--accent))]">
                  <td className="px-4 py-3">
                    <div>
                      <p className="text-sm font-medium">{user.display_name}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">@{user.username}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">{user.email}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {user.roles.map((roleName) => {
                        const roleObj = roles?.find((r) => r.display_name === roleName);
                        return (
                          <span
                            key={roleName}
                            className="px-1.5 py-0.5 bg-[hsl(var(--accent))] rounded text-xs cursor-pointer hover:bg-red-100 group"
                            onClick={() => roleObj && removeRole.mutate({ userId: user.id, roleId: roleObj.id })}
                            title="Click to remove"
                          >
                            {roleName}
                          </span>
                        );
                      })}
                      {(pendingRolesByUser.get(user.id) ?? []).map((cr) => {
                        const snap = cr as unknown as { snapshot?: { role_display_name?: string } };
                        const label = snap.snapshot?.role_display_name ?? "role";
                        return (
                          <span
                            key={cr.id}
                            className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                              cr.action === "create"
                                ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                : "bg-red-500/20 text-red-400 border border-red-500/30 line-through"
                            }`}
                            title={`Pending ${cr.action}: ${label} (${cr.status})`}
                          >
                            {cr.action === "create" ? "+" : "-"}{label}
                          </span>
                        );
                      })}
                      <button
                        onClick={() => { setSelectedUser(user); setShowRoleModal(true); }}
                        className="px-1.5 py-0.5 border border-dashed border-[hsl(var(--border))] rounded text-xs text-[hsl(var(--muted-foreground))] hover:border-[hsl(var(--primary))]"
                      >
                        +
                      </button>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {user.is_mfa_enabled ? (
                      <span className="text-xs text-green-600 flex items-center gap-1">
                        <Shield className="w-3 h-3" /> Enabled
                      </span>
                    ) : (
                      <span className="text-xs text-[hsl(var(--muted-foreground))]">Off</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      user.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                    }`}>
                      {user.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-[hsl(var(--muted-foreground))]">
                    {user.last_login_at ? formatDate(user.last_login_at) : "Never"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleActive.mutate(user)}
                      className={`p-1 rounded ${
                        user.is_active
                          ? "text-red-500 hover:bg-red-50"
                          : "text-green-500 hover:bg-green-50"
                      }`}
                      title={user.is_active ? "Deactivate" : "Activate"}
                    >
                      {user.is_active ? <UserX className="w-4 h-4" /> : <UserCheck className="w-4 h-4" />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {users && users.meta.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-sm border border-[hsl(var(--border))] rounded disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-[hsl(var(--muted-foreground))]">
            Page {page} of {users.meta.total_pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(users.meta.total_pages, p + 1))}
            disabled={page === users.meta.total_pages}
            className="px-3 py-1 text-sm border border-[hsl(var(--border))] rounded disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[hsl(var(--background))] rounded-lg p-6 w-full max-w-md border border-[hsl(var(--border))]">
            {createdUser ? (
              <>
                <h2 className="text-lg font-semibold mb-4">User Created Successfully</h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-[hsl(var(--muted-foreground))]">Username</p>
                    <p className="text-sm font-medium">{createdUser.username}</p>
                  </div>
                  <div>
                    <p className="text-sm text-[hsl(var(--muted-foreground))]">Email</p>
                    <p className="text-sm font-medium">{createdUser.email}</p>
                  </div>
                  <div className="p-3 bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 rounded-md">
                    <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200 mb-1">
                      Temporary Password
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 text-sm font-mono bg-[hsl(var(--accent))] px-2 py-1 rounded break-all">
                        {createdUser.temporary_password}
                      </code>
                      <button
                        onClick={handleCopyPassword}
                        className="p-1.5 rounded hover:bg-[hsl(var(--accent))]"
                        title="Copy password"
                      >
                        {copied ? (
                          <Check className="w-4 h-4 text-green-600" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-2">
                      The user will be required to change this password on first login. Copy it now — it cannot be retrieved later.
                    </p>
                  </div>
                </div>
                <button
                  onClick={handleCloseCreateModal}
                  className="mt-4 w-full px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm hover:opacity-90"
                >
                  Done
                </button>
              </>
            ) : (
              <>
                <h2 className="text-lg font-semibold mb-4">Add New User</h2>
                {createError && (
                  <div className="mb-4 p-3 rounded-md bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 text-sm">
                    {createError}
                  </div>
                )}
                <form onSubmit={handleCreateSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Username</label>
                    <input
                      type="text"
                      value={createForm.username}
                      onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
                      className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-transparent"
                      required
                      minLength={3}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Email</label>
                    <input
                      type="email"
                      value={createForm.email}
                      onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                      className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-transparent"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Display Name</label>
                    <input
                      type="text"
                      value={createForm.display_name}
                      onChange={(e) => setCreateForm((f) => ({ ...f, display_name: e.target.value }))}
                      className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-transparent"
                      required
                    />
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    A secure password will be automatically generated. The user must change it on first login.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleCloseCreateModal}
                      className="flex-1 px-4 py-2 border border-[hsl(var(--border))] rounded-md text-sm"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={createUser.isPending}
                      className="flex-1 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm hover:opacity-90 disabled:opacity-50"
                    >
                      {createUser.isPending ? "Creating..." : "Create User"}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}

      {/* Assign Role Modal */}
      {showRoleModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[hsl(var(--background))] rounded-lg p-6 w-full max-w-sm border border-[hsl(var(--border))]">
            <h2 className="text-lg font-semibold mb-4">
              Assign Role to {selectedUser.display_name}
            </h2>
            <div className="space-y-2 max-h-64 overflow-auto">
              {roles?.map((role) => {
                const alreadyAssigned = selectedUser.roles.includes(role.display_name);
                return (
                  <button
                    key={role.id}
                    onClick={() => handleAssignRole(selectedUser.id, role.id)}
                    disabled={alreadyAssigned}
                    className="w-full text-left px-3 py-2 border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))] disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">{role.display_name}</p>
                        {role.description && (
                          <p className="text-xs text-[hsl(var(--muted-foreground))]">{role.description}</p>
                        )}
                      </div>
                      {alreadyAssigned && (
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">Assigned</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setShowRoleModal(false)}
              className="mt-4 w-full px-4 py-2 border border-[hsl(var(--border))] rounded-md text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
