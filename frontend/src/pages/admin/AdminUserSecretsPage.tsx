import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { Trash2 } from "lucide-react";

interface AdminUserSecret {
  id: string;
  user_id: string;
  username: string | null;
  name: string;
  description: string | null;
  sensitive: boolean;
  created_at: string;
  updated_at: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number; page: number; per_page: number; total_pages: number };
}

export function AdminUserSecretsPage() {
  const queryClient = useQueryClient();

  const { data: secretsResponse, isLoading } = useQuery({
    queryKey: ["admin-user-secrets"],
    queryFn: () =>
      api.get<PaginatedResponse<AdminUserSecret>>("/user-secrets/admin/all?per_page=100"),
  });

  const secrets = secretsResponse?.data ?? [];

  const deleteSecret = useToastMutation({
    mutationFn: (id: string) => api.delete(`/user-secrets/admin/${id}`),
    loadingMessage: "Deleting secret...",
    successMessage: "Secret deleted.",
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["admin-user-secrets"] }),
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">User Secrets</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          All user secrets across the platform. Values are never visible to admins.
        </p>
      </div>

      {isLoading ? (
        <p className="text-[var(--color-text-muted)]">Loading...</p>
      ) : secrets.length === 0 ? (
        <div className="text-center py-12 text-[var(--color-text-muted)]">
          <p>No user secrets exist yet.</p>
        </div>
      ) : (
        <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-surface-2)]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">User</th>
                <th className="text-left px-4 py-2 font-medium">Secret Name</th>
                <th className="text-left px-4 py-2 font-medium">Description</th>
                <th className="text-left px-4 py-2 font-medium">Mode</th>
                <th className="text-left px-4 py-2 font-medium">Created</th>
                <th className="text-right px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {secrets.map((s) => (
                <tr key={s.id} className="hover:bg-[var(--color-surface-2)]/50">
                  <td className="px-4 py-2 font-mono text-xs">
                    {s.username || s.user_id}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">{s.name}</td>
                  <td className="px-4 py-2 text-[var(--color-text-muted)] max-w-[200px] truncate">
                    {s.description || "-"}
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {s.sensitive ? (
                      <span className="px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-[10px] font-medium">
                        SENSITIVE
                      </span>
                    ) : (
                      <span className="text-[var(--color-text-muted)]">standard</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-[var(--color-text-muted)]">
                    {new Date(s.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => {
                        if (
                          confirm(
                            `Delete secret "${s.name}" belonging to ${s.username || "user"}?`
                          )
                        ) {
                          deleteSecret.mutate(s.id);
                        }
                      }}
                      className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
