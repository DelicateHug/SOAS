import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate, issueStatusColors, issueStatusLabels } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { CircleDot, Plus, Search } from "lucide-react";
import type { PaginatedResponse, IssueItem, IssueStatus } from "@/types/api";

const STATUSES: IssueStatus[] = ["open", "in_progress", "resolved", "closed", "wont_fix"];

export function IssueListPage() {
  const { hasPermission } = useAuthStore();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["issues", statusFilter, search, page],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (search) params.set("search", search);
      params.set("page", String(page));
      params.set("per_page", "25");
      return api.get<PaginatedResponse<IssueItem>>(`/issues?${params}`);
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Issues</h1>
        {hasPermission("issue:create") && (
          <Link
            to="/issues/new"
            className="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 text-sm"
          >
            <Plus className="w-4 h-4" />
            New Issue
          </Link>
        )}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{issueStatusLabels[s]}</option>
          ))}
        </select>
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search issues..."
            className="w-full pl-9 pr-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : data?.data.length === 0 ? (
        <div className="flex flex-col items-center py-12 text-[var(--color-text-muted)]">
          <CircleDot className="w-12 h-12 mb-3" />
          <p>No issues found</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {data?.data.map((issue) => (
              <Link
                key={issue.id}
                to={`/issues/${issue.id}`}
                className="border border-[var(--color-border)] rounded-lg p-4 hover:bg-[var(--color-surface-2)] transition-colors"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{issue.title}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded ${issueStatusColors[issue.status] ?? "bg-gray-500/15 text-gray-400"}`}>
                    {issueStatusLabels[issue.status] ?? issue.status}
                  </span>
                </div>
                <div className="flex flex-wrap gap-4 mt-2 text-sm text-[var(--color-text-muted)]">
                  {issue.assigned_to && (
                    <span>Assigned: {issue.assigned_to.display_name}</span>
                  )}
                  <span>By {issue.created_by.display_name}</span>
                  {issue.link_count > 0 && (
                    <span>{issue.link_count} linked</span>
                  )}
                  {issue.checklist_total > 0 && (
                    <span>Checklist: {issue.checklist_checked}/{issue.checklist_total}</span>
                  )}
                  {issue.note_count > 0 && (
                    <span>{issue.note_count} notes</span>
                  )}
                  <span>Created {formatDate(issue.created_at)}</span>
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {data && data.meta.total_pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1 text-sm border border-[var(--color-border)] rounded-md disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-[var(--color-text-muted)]">
                Page {page} of {data.meta.total_pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.meta.total_pages, p + 1))}
                disabled={page >= data.meta.total_pages}
                className="px-3 py-1 text-sm border border-[var(--color-border)] rounded-md disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
