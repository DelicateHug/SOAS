import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { caseStatusColors, priorityColors, priorityLabels, formatDate } from "@/lib/utils";
import { FolderPlus } from "lucide-react";
import { ProductionGuard } from "@/components/ui/ProductionGuard";
import { CreateGroupModal } from "@/pages/incidents/CreateGroupModal";
import type { PaginatedResponse, CaseItem, CaseStatus } from "@/types/api";
import { useTeamStore } from "@/stores/teamStore";

const caseStatuses: CaseStatus[] = ["open", "investigating", "pending", "closed", "archived"];
const priorities = [1, 2, 3, 4, 5];

export function CaseListPage() {
  const [filters, setFilters] = useState({ status: "", priority: "", page: 1 });
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const activeTeamId = useTeamStore((s) => s.activeTeamId);

  const { data, isLoading } = useQuery({
    queryKey: ["cases", filters, activeTeamId],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.priority) params.set("priority", filters.priority);
      params.set("team_id", activeTeamId!);
      params.set("page", String(filters.page));
      params.set("per_page", "25");
      return api.get<PaginatedResponse<CaseItem>>(`/cases?${params}`);
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Incident Groups</h1>
        <ProductionGuard>
          <button
            onClick={() => setShowCreateGroup(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm hover:opacity-90"
          >
            <FolderPlus className="w-4 h-4" /> New Group
          </button>
        </ProductionGuard>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
          className="px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
        >
          <option value="">All Statuses</option>
          {caseStatuses.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filters.priority}
          onChange={(e) => setFilters({ ...filters, priority: e.target.value, page: 1 })}
          className="px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
        >
          <option value="">All Priorities</option>
          {priorities.map((p) => (
            <option key={p} value={String(p)}>{priorityLabels[p]}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
              <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Priority</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Title</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Lead</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Created</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Incidents</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[hsl(var(--border))]">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                  Loading...
                </td>
              </tr>
            ) : data?.data.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                  No incident groups found
                </td>
              </tr>
            ) : (
              data?.data.map((group) => (
                <tr key={group.id} className="hover:bg-[hsl(var(--accent))]">
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${priorityColors[group.priority]}`}>
                      {priorityLabels[group.priority] ?? `P${group.priority}`}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${caseStatusColors[group.status]}`}>
                      {group.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/cases/${group.id}`}
                      className="text-sm text-[hsl(var(--primary))] hover:underline"
                    >
                      {group.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-[hsl(var(--muted-foreground))]">
                    {group.lead?.display_name || "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-[hsl(var(--muted-foreground))]">
                    {formatDate(group.created_at)}
                  </td>
                  <td className="px-4 py-3 text-sm text-[hsl(var(--muted-foreground))]">
                    {group.incident_count}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {data && data.meta.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          {Array.from({ length: data.meta.total_pages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              onClick={() => setFilters({ ...filters, page })}
              className={`px-3 py-1 rounded text-sm ${
                page === filters.page
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                  : "border border-[hsl(var(--border))]"
              }`}
            >
              {page}
            </button>
          ))}
        </div>
      )}

      {showCreateGroup && (
        <CreateGroupModal onClose={() => setShowCreateGroup(false)} />
      )}
    </div>
  );
}
