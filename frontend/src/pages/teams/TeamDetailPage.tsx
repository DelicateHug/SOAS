import { useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  Crown,
  Lock,
  Pencil,
  Plus,
  Shield,
  Trash2,
  UserMinus,
  Variable,
} from "lucide-react";
import type { Team, TeamMember, PaginatedResponse, Role } from "@/types/api";
import { useAuthStore } from "@/stores/authStore";
import { useToastMutation } from "@/hooks/useToastMutation";

interface UserListItem {
  id: string;
  username: string;
  display_name: string;
}

interface TeamVariable {
  id: string;
  team_id: string;
  name: string;
  description?: string;
  value: unknown;
  is_secret: boolean;
  created_by?: string;
  updated_by?: string;
  created_at: string;
  updated_at: string;
}

interface VariablePermission {
  role_id: string;
  role_name?: string;
  can_read: boolean;
  can_write: boolean;
}

export function TeamDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "members";
  const currentUser = useAuthStore((s) => s.user);
  const refreshSession = useAuthStore((s) => s.refreshSession);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ display_name: "", description: "" });
  const [showAddMember, setShowAddMember] = useState(false);
  const [addForm, setAddForm] = useState({ user_id: "", role_ids: [] as string[], team_role: "member" });
  const [editingMember, setEditingMember] = useState<string | null>(null);
  const [memberEditForm, setMemberEditForm] = useState({ role_ids: [] as string[], team_role: "" });

  // Variable state
  const [showAddVar, setShowAddVar] = useState(false);
  const [varForm, setVarForm] = useState({ name: "", description: "", value: "", is_secret: false });
  const [editingVar, setEditingVar] = useState<string | null>(null);
  const [varEditForm, setVarEditForm] = useState({ description: "", value: "", is_secret: false });
  const [permVar, setPermVar] = useState<TeamVariable | null>(null);
  const [permEntries, setPermEntries] = useState<VariablePermission[]>([]);

  const { data: team, isLoading } = useQuery({
    queryKey: ["team", id],
    queryFn: () => api.get<Team>(`/teams/${id}`),
    enabled: !!id,
  });

  const { data: members } = useQuery({
    queryKey: ["team-members", id],
    queryFn: () => api.get<TeamMember[]>(`/teams/${id}/members`),
    enabled: !!id,
  });

  const { data: roles } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });

  const { data: allUsers } = useQuery({
    queryKey: ["users-list"],
    queryFn: () => api.get<PaginatedResponse<UserListItem>>("/admin/users?per_page=100"),
    enabled: showAddMember,
  });

  const { data: varsResponse } = useQuery({
    queryKey: ["team-variables", id],
    queryFn: () => api.get<PaginatedResponse<TeamVariable>>(`/teams/${id}/variables?per_page=100`),
    enabled: !!id && activeTab === "variables",
  });
  const variables = varsResponse?.data ?? [];

  const isOwner = members?.some(
    (m) => m.user_id === currentUser?.id && m.team_role === "owner"
  );
  const isAdmin = currentUser?.roles?.includes("admin");
  const canManage = isOwner || isAdmin;

  const updateTeam = useToastMutation({
    mutationFn: () =>
      api.patch<Team>(`/teams/${id}`, {
        display_name: editForm.display_name,
        description: editForm.description || null,
      }),
    successMessage: "Team updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", id] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setEditing(false);
    },
  });

  const deleteTeam = useToastMutation({
    mutationFn: () => api.delete(`/teams/${id}`),
    successMessage: "Team deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      navigate("/teams");
    },
  });

  const addMember = useToastMutation({
    mutationFn: () =>
      api.post(`/teams/${id}/members`, {
        user_id: addForm.user_id,
        role_ids: addForm.role_ids,
        team_role: addForm.team_role,
      }),
    successMessage: "Member added.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-members", id] });
      queryClient.invalidateQueries({ queryKey: ["team", id] });
      setShowAddMember(false);
      setAddForm({ user_id: "", role_ids: [], team_role: "member" });
      refreshSession();
    },
  });

  const updateMember = useToastMutation({
    mutationFn: (userId: string) =>
      api.patch(`/teams/${id}/members/${userId}`, {
        role_ids: memberEditForm.role_ids.length > 0 ? memberEditForm.role_ids : undefined,
        team_role: memberEditForm.team_role || undefined,
      }),
    successMessage: "Member updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-members", id] });
      setEditingMember(null);
    },
  });

  const removeMember = useToastMutation({
    mutationFn: (userId: string) => api.delete(`/teams/${id}/members/${userId}`),
    successMessage: "Member removed.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-members", id] });
      queryClient.invalidateQueries({ queryKey: ["team", id] });
    },
  });

  // Variable mutations
  const createVar = useToastMutation({
    mutationFn: () => {
      let parsedValue: unknown = varForm.value;
      try { parsedValue = JSON.parse(varForm.value); } catch { /* keep as string */ }
      return api.post(`/teams/${id}/variables`, {
        name: varForm.name,
        description: varForm.description || null,
        value: parsedValue,
        is_secret: varForm.is_secret,
      });
    },
    successMessage: "Variable created.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-variables", id] });
      setShowAddVar(false);
      setVarForm({ name: "", description: "", value: "", is_secret: false });
    },
  });

  const updateVar = useToastMutation({
    mutationFn: (varId: string) => {
      let parsedValue: unknown = varEditForm.value;
      try { parsedValue = JSON.parse(varEditForm.value); } catch { /* keep as string */ }
      return api.patch(`/teams/${id}/variables/${varId}`, {
        description: varEditForm.description || null,
        value: parsedValue,
        is_secret: varEditForm.is_secret,
      });
    },
    successMessage: "Variable updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-variables", id] });
      setEditingVar(null);
    },
  });

  const deleteVar = useToastMutation({
    mutationFn: (varId: string) => api.delete(`/teams/${id}/variables/${varId}`),
    successMessage: "Variable deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-variables", id] });
    },
  });

  const savePermissions = useToastMutation({
    mutationFn: () =>
      api.patch(`/teams/${id}/variables/${permVar!.id}/permissions`, {
        permissions: permEntries.filter((p) => p.can_read || p.can_write),
      }),
    successMessage: "Permissions updated.",
    onSuccess: () => {
      setPermVar(null);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--primary))]" />
      </div>
    );
  }

  if (!team) {
    return <div className="text-center py-16 text-[hsl(var(--muted-foreground))]">Team not found.</div>;
  }

  const existingUserIds = new Set(members?.map((m) => m.user_id) ?? []);
  const availableUsers = (allUsers?.data ?? []).filter((u) => !existingUserIds.has(u.id));

  const openPermissions = async (v: TeamVariable) => {
    setPermVar(v);
    try {
      const perms = await api.get<VariablePermission[]>(`/teams/${id}/variables/${v.id}/permissions`);
      const allRoles = roles ?? [];
      const permMap = new Map(perms.map((p) => [p.role_id, p]));
      setPermEntries(
        allRoles.map((r) => ({
          role_id: r.id,
          role_name: r.name,
          can_read: permMap.get(r.id)?.can_read ?? false,
          can_write: permMap.get(r.id)?.can_write ?? false,
        }))
      );
    } catch {
      setPermEntries(
        (roles ?? []).map((r) => ({ role_id: r.id, role_name: r.name, can_read: false, can_write: false }))
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/teams")}
          className="p-1.5 rounded-md hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          {editing ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                updateTeam.mutate();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={editForm.display_name}
                onChange={(e) => setEditForm((f) => ({ ...f, display_name: e.target.value }))}
                className="text-2xl font-bold bg-transparent border-b border-[hsl(var(--border))] focus:border-[hsl(var(--primary))] outline-none"
              />
              <button
                type="submit"
                disabled={updateTeam.isPending}
                className="px-3 py-1 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="px-3 py-1 text-sm rounded border border-[hsl(var(--border))]"
              >
                Cancel
              </button>
            </form>
          ) : (
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{team.display_name}</h1>
              {team.is_default && (
                <span className="text-xs px-2 py-0.5 rounded bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]">
                  Default
                </span>
              )}
              {canManage && (
                <button
                  onClick={() => {
                    setEditForm({ display_name: team.display_name, description: team.description || "" });
                    setEditing(true);
                  }}
                  className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                >
                  <Pencil className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            {team.description || "No description."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canManage && !team.is_default && (
            <button
              onClick={() => {
                if (confirm("Delete this team? Resources will become unscoped.")) {
                  deleteTeam.mutate();
                }
              }}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md text-red-400 border border-red-500/30 hover:bg-red-500/10"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          )}
        </div>
      </div>

      {/* Info bar */}
      <div className="flex items-center gap-6 text-sm text-[hsl(var(--muted-foreground))]">
        <span>Slug: <code className="text-xs bg-[hsl(var(--accent))] px-1.5 py-0.5 rounded">{team.name}</code></span>
        <span>{team.member_count} member{team.member_count !== 1 ? "s" : ""}</span>
        <span>Created {formatDate(team.created_at)}</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[hsl(var(--border))]">
        {[
          { key: "members", label: "Members" },
          { key: "variables", label: "Variables" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSearchParams({ tab: tab.key })}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.key
                ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
                : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Members Tab */}
      {activeTab === "members" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Members</h2>
            {canManage && (
              <button
                onClick={() => setShowAddMember(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90"
              >
                <Plus className="w-4 h-4" />
                Add Member
              </button>
            )}
          </div>

          <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--accent))]/50">
                  <th className="text-left px-4 py-2.5 font-medium">User</th>
                  <th className="text-left px-4 py-2.5 font-medium">Team Role</th>
                  <th className="text-left px-4 py-2.5 font-medium">Permission Roles</th>
                  <th className="text-left px-4 py-2.5 font-medium">Joined</th>
                  {canManage && <th className="text-right px-4 py-2.5 font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {(members ?? []).map((member) => (
                  <tr key={member.user_id} className="border-b border-[hsl(var(--border))] last:border-0">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-[hsl(var(--primary))] flex items-center justify-center text-[hsl(var(--primary-foreground))] text-xs font-medium">
                          {member.display_name?.charAt(0).toUpperCase() || "?"}
                        </div>
                        <div>
                          <p className="font-medium">{member.display_name}</p>
                          <p className="text-xs text-[hsl(var(--muted-foreground))]">@{member.username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {editingMember === member.user_id ? (
                        <select
                          value={memberEditForm.team_role}
                          onChange={(e) => setMemberEditForm((f) => ({ ...f, team_role: e.target.value }))}
                          className="px-2 py-1 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                        >
                          <option value="member">Member</option>
                          <option value="owner">Owner</option>
                        </select>
                      ) : (
                        <span className="inline-flex items-center gap-1">
                          {member.team_role === "owner" && <Crown className="w-3.5 h-3.5 text-yellow-500" />}
                          <span className="capitalize">{member.team_role}</span>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {editingMember === member.user_id ? (
                        <div className="flex flex-wrap gap-1.5">
                          {(roles ?? []).map((r) => (
                            <label key={r.id} className="inline-flex items-center gap-1 text-xs cursor-pointer">
                              <input
                                type="checkbox"
                                checked={memberEditForm.role_ids.includes(r.id)}
                                onChange={(e) => {
                                  setMemberEditForm((f) => ({
                                    ...f,
                                    role_ids: e.target.checked
                                      ? [...f.role_ids, r.id]
                                      : f.role_ids.filter((rid) => rid !== r.id),
                                  }));
                                }}
                                className="rounded border-[hsl(var(--border))]"
                              />
                              {r.display_name}
                            </label>
                          ))}
                        </div>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {member.roles.map((r) => (
                            <span key={r.id} className="text-xs px-2 py-0.5 rounded bg-[hsl(var(--accent))]">
                              {r.display_name}
                            </span>
                          ))}
                          {member.roles.length === 0 && (
                            <span className="text-xs text-[hsl(var(--muted-foreground))]">No roles</span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                      {formatDate(member.joined_at)}
                    </td>
                    {canManage && (
                      <td className="px-4 py-3 text-right">
                        {editingMember === member.user_id ? (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => updateMember.mutate(member.user_id)}
                              disabled={updateMember.isPending}
                              className="px-2 py-1 text-xs rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingMember(null)}
                              className="px-2 py-1 text-xs rounded border border-[hsl(var(--border))]"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => {
                                setEditingMember(member.user_id);
                                setMemberEditForm({
                                  role_ids: member.roles.map((r) => r.id),
                                  team_role: member.team_role,
                                });
                              }}
                              className="p-1.5 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
                              title="Edit role"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                if (confirm(`Remove ${member.display_name} from this team?`)) {
                                  removeMember.mutate(member.user_id);
                                }
                              }}
                              className="p-1.5 rounded hover:bg-red-500/10 text-[hsl(var(--muted-foreground))] hover:text-red-400"
                              title="Remove member"
                            >
                              <UserMinus className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
                {(members ?? []).length === 0 && (
                  <tr>
                    <td colSpan={canManage ? 5 : 4} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      No members yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Variables Tab */}
      {activeTab === "variables" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Team Variables</h2>
            {canManage && (
              <button
                onClick={() => setShowAddVar(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90"
              >
                <Plus className="w-4 h-4" />
                Add Variable
              </button>
            )}
          </div>

          <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--accent))]/50">
                  <th className="text-left px-4 py-2.5 font-medium">Name</th>
                  <th className="text-left px-4 py-2.5 font-medium">Value</th>
                  <th className="text-left px-4 py-2.5 font-medium">Description</th>
                  <th className="text-left px-4 py-2.5 font-medium">Updated</th>
                  {canManage && <th className="text-right px-4 py-2.5 font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {variables.map((v) => (
                  <tr key={v.id} className="border-b border-[hsl(var(--border))] last:border-0">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {v.is_secret && <Lock className="w-3.5 h-3.5 text-yellow-500" />}
                        <span className="font-mono text-sm">{v.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {editingVar === v.id ? (
                        <input
                          value={varEditForm.value}
                          onChange={(e) => setVarEditForm((f) => ({ ...f, value: e.target.value }))}
                          className="w-full px-2 py-1 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm font-mono"
                        />
                      ) : (
                        <span className="text-sm font-mono text-[hsl(var(--muted-foreground))]">
                          {v.is_secret ? "***" : typeof v.value === "string" ? v.value : JSON.stringify(v.value)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                      {editingVar === v.id ? (
                        <input
                          value={varEditForm.description}
                          onChange={(e) => setVarEditForm((f) => ({ ...f, description: e.target.value }))}
                          className="w-full px-2 py-1 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                        />
                      ) : (
                        v.description || "-"
                      )}
                    </td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                      {formatDate(v.updated_at)}
                    </td>
                    {canManage && (
                      <td className="px-4 py-3 text-right">
                        {editingVar === v.id ? (
                          <div className="flex items-center justify-end gap-1">
                            <label className="inline-flex items-center gap-1 text-xs mr-2">
                              <input
                                type="checkbox"
                                checked={varEditForm.is_secret}
                                onChange={(e) => setVarEditForm((f) => ({ ...f, is_secret: e.target.checked }))}
                              />
                              Secret
                            </label>
                            <button
                              onClick={() => updateVar.mutate(v.id)}
                              disabled={updateVar.isPending}
                              className="px-2 py-1 text-xs rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingVar(null)}
                              className="px-2 py-1 text-xs rounded border border-[hsl(var(--border))]"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => openPermissions(v)}
                              className="p-1.5 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
                              title="Manage permissions"
                            >
                              <Shield className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                setEditingVar(v.id);
                                setVarEditForm({
                                  description: v.description || "",
                                  value: v.is_secret ? "" : (typeof v.value === "string" ? v.value : JSON.stringify(v.value ?? "")),
                                  is_secret: v.is_secret,
                                });
                              }}
                              className="p-1.5 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
                              title="Edit variable"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                if (confirm(`Delete variable "${v.name}"?`)) {
                                  deleteVar.mutate(v.id);
                                }
                              }}
                              className="p-1.5 rounded hover:bg-red-500/10 text-[hsl(var(--muted-foreground))] hover:text-red-400"
                              title="Delete variable"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
                {variables.length === 0 && (
                  <tr>
                    <td colSpan={canManage ? 5 : 4} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      <Variable className="w-8 h-8 mx-auto mb-2 opacity-40" />
                      No team variables yet.
                      {canManage && " Click \"Add Variable\" to create one."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add Member Modal */}
      {showAddMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] rounded-lg border border-[hsl(var(--border))] p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Add Member</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                addMember.mutate();
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">User</label>
                <select
                  value={addForm.user_id}
                  onChange={(e) => setAddForm((f) => ({ ...f, user_id: e.target.value }))}
                  required
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                >
                  <option value="">Select a user...</option>
                  {availableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.display_name} (@{u.username})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Permission Roles</label>
                <div className="space-y-1.5 p-2 border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--background))]">
                  {(roles ?? []).map((r) => (
                    <label key={r.id} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={addForm.role_ids.includes(r.id)}
                        onChange={(e) => {
                          setAddForm((f) => ({
                            ...f,
                            role_ids: e.target.checked
                              ? [...f.role_ids, r.id]
                              : f.role_ids.filter((rid) => rid !== r.id),
                          }));
                        }}
                        className="rounded border-[hsl(var(--border))]"
                      />
                      {r.display_name}
                    </label>
                  ))}
                </div>
                {addForm.role_ids.length === 0 && (
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">Select at least one role.</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Team Role</label>
                <select
                  value={addForm.team_role}
                  onChange={(e) => setAddForm((f) => ({ ...f, team_role: e.target.value }))}
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                >
                  <option value="member">Member</option>
                  <option value="owner">Owner</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddMember(false)}
                  className="px-4 py-2 text-sm rounded-md border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addMember.isPending || addForm.role_ids.length === 0}
                  className="px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
                >
                  {addMember.isPending ? "Adding..." : "Add"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Variable Modal */}
      {showAddVar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] rounded-lg border border-[hsl(var(--border))] p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Add Team Variable</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createVar.mutate();
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  value={varForm.name}
                  onChange={(e) => setVarForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="VARIABLE_NAME"
                  required
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Value</label>
                <textarea
                  value={varForm.value}
                  onChange={(e) => setVarForm((f) => ({ ...f, value: e.target.value }))}
                  placeholder="Value (string or JSON)"
                  rows={3}
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm font-mono resize-y"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <input
                  value={varForm.description}
                  onChange={(e) => setVarForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="What this variable is for..."
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                />
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={varForm.is_secret}
                  onChange={(e) => setVarForm((f) => ({ ...f, is_secret: e.target.checked }))}
                />
                Secret (value will be masked in the UI)
              </label>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddVar(false)}
                  className="px-4 py-2 text-sm rounded-md border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createVar.isPending || !varForm.name.trim()}
                  className="px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
                >
                  {createVar.isPending ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Variable Permissions Modal */}
      {permVar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] rounded-lg border border-[hsl(var(--border))] p-6 w-full max-w-lg">
            <h2 className="text-lg font-semibold mb-1">
              Permissions: <span className="font-mono">{permVar.name}</span>
            </h2>
            <p className="text-sm text-[hsl(var(--muted-foreground))] mb-4">
              Control which roles can read or write this variable.
            </p>
            <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden mb-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--accent))]/50">
                    <th className="text-left px-4 py-2 font-medium">Role</th>
                    <th className="text-center px-4 py-2 font-medium w-20">Read</th>
                    <th className="text-center px-4 py-2 font-medium w-20">Write</th>
                  </tr>
                </thead>
                <tbody>
                  {permEntries.map((entry, i) => (
                    <tr key={entry.role_id} className="border-b border-[hsl(var(--border))] last:border-0">
                      <td className="px-4 py-2">{entry.role_name}</td>
                      <td className="px-4 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={entry.can_read}
                          onChange={(e) => {
                            const updated = [...permEntries];
                            updated[i] = { ...updated[i], can_read: e.target.checked };
                            setPermEntries(updated);
                          }}
                        />
                      </td>
                      <td className="px-4 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={entry.can_write}
                          onChange={(e) => {
                            const updated = [...permEntries];
                            updated[i] = { ...updated[i], can_write: e.target.checked };
                            setPermEntries(updated);
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setPermVar(null)}
                className="px-4 py-2 text-sm rounded-md border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
              >
                Cancel
              </button>
              <button
                onClick={() => savePermissions.mutate()}
                disabled={savePermissions.isPending}
                className="px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
              >
                {savePermissions.isPending ? "Saving..." : "Save Permissions"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
