import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UsersRound, Plus } from "lucide-react";
import type { PaginatedResponse, Team } from "@/types/api";
import { useAuthStore } from "@/stores/authStore";
import { useToastMutation } from "@/hooks/useToastMutation";

export function TeamsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission, refreshSession } = useAuthStore();
  const canCreate = hasPermission("team:create");
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", display_name: "", description: "" });

  // Always scoped to current user's teams — no "all teams" view
  const { data, isLoading } = useQuery({
    queryKey: ["teams", page],
    queryFn: () => api.get<PaginatedResponse<Team>>(`/teams?page=${page}&per_page=25`),
  });

  const createTeam = useToastMutation({
    mutationFn: () =>
      api.post<Team>("/teams", {
        name: createForm.name,
        display_name: createForm.display_name,
        description: createForm.description || undefined,
      }),
    successMessage: "Team created.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setShowCreateModal(false);
      setCreateForm({ name: "", display_name: "", description: "" });
      // Refresh JWT so new team appears in sidebar selector
      refreshSession();
    },
  });

  const teams = data?.data ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">My Teams</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            Teams you are a member of. Select a team in the sidebar to scope all data views.
          </p>
        </div>
        {canCreate && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] text-sm font-medium hover:opacity-90"
          >
            <Plus className="w-4 h-4" />
            Create Team
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--primary))]" />
        </div>
      ) : teams.length === 0 ? (
        <div className="text-center py-16 text-[hsl(var(--muted-foreground))]">
          <UsersRound className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p>You are not a member of any teams.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {teams.map((team) => (
              <button
                key={team.id}
                onClick={() => navigate(`/teams/${team.id}`)}
                className="text-left p-5 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] hover:border-[hsl(var(--primary))] transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <UsersRound className="w-5 h-5 text-[hsl(var(--primary))]" />
                    <h3 className="font-semibold">{team.display_name}</h3>
                  </div>
                  {team.is_default && (
                    <span className="text-xs px-2 py-0.5 rounded bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]">
                      Default
                    </span>
                  )}
                </div>
                {team.description && (
                  <p className="text-sm text-[hsl(var(--muted-foreground))] mb-3 line-clamp-2">
                    {team.description}
                  </p>
                )}
                <div className="flex items-center justify-between text-xs text-[hsl(var(--muted-foreground))]">
                  <span>{team.member_count} member{team.member_count !== 1 ? "s" : ""}</span>
                  <span>Created {formatDate(team.created_at)}</span>
                </div>
              </button>
            ))}
          </div>

          {meta && meta.total_pages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded text-sm border border-[hsl(var(--border))] disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-[hsl(var(--muted-foreground))]">
                Page {page} of {meta.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))}
                disabled={page === meta.total_pages}
                className="px-3 py-1 rounded text-sm border border-[hsl(var(--border))] disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Create Team Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] rounded-lg border border-[hsl(var(--border))] p-6 w-full max-w-md">
            <h2 className="text-lg font-semibold mb-4">Create Team</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createTeam.mutate();
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">Name (URL-safe slug)</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="alpha-team"
                  pattern="[a-z0-9][a-z0-9-]*[a-z0-9]"
                  required
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Display Name</label>
                <input
                  type="text"
                  value={createForm.display_name}
                  onChange={(e) => setCreateForm((f) => ({ ...f, display_name: e.target.value }))}
                  placeholder="Alpha Team"
                  required
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Optional description..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-sm resize-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm rounded-md border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTeam.isPending}
                  className="px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
                >
                  {createTeam.isPending ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
