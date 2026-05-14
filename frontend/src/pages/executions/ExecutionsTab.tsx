import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/utils";
import { Terminal, Clock } from "lucide-react";
import {
  ExecutionFilters,
  emptyExecutionFilters,
  type ExecutionFilterValues,
} from "./ExecutionFilters";
import type { PaginatedResponse, ExecutionItem } from "@/types/api";

const statusColors: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800",
  queued: "bg-blue-100 text-blue-800",
  running: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-500",
  timed_out: "bg-orange-100 text-orange-800",
};

export function ExecutionsTab() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ExecutionFilterValues>(
    emptyExecutionFilters
  );

  const handleFilterChange = (newFilters: ExecutionFilterValues) => {
    setFilters(newFilters);
    setPage(1);
  };

  const { data: executions, isLoading } = useQuery({
    queryKey: ["executions", { page, ...filters }],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: "25",
      });
      if (filters.status) params.set("status", filters.status);
      if (filters.automationId)
        params.set("automation_id", filters.automationId);
      if (filters.startedAfter)
        params.set(
          "started_after",
          new Date(filters.startedAfter).toISOString()
        );
      if (filters.startedBefore)
        params.set(
          "started_before",
          new Date(filters.startedBefore).toISOString()
        );
      return api.get<PaginatedResponse<ExecutionItem>>(
        `/executions?${params}`
      );
    },
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasActive = data?.data.some(
        (e) => e.status === "running" || e.status === "queued" || e.status === "pending"
      );
      return hasActive ? 5000 : false;
    },
  });

  const { data: pendingInputData } = useQuery({
    queryKey: ["pending-input"],
    queryFn: () => api.get<{ execution_ids: string[] }>("/executions/pending-input"),
    refetchInterval: () => {
      const hasActive = executions?.data.some(
        (e) => e.status === "running" || e.status === "queued" || e.status === "pending"
      );
      return hasActive ? 5000 : false;
    },
  });
  const pendingInputIds = new Set(pendingInputData?.execution_ids || []);

  return (
    <div>
      <ExecutionFilters filters={filters} onChange={handleFilterChange} />

      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="border border-[var(--color-border)] rounded-lg">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-sm text-[var(--color-text-muted)]">
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Automation</th>
                <th className="px-4 py-3 font-medium">Triggered By</th>
                <th className="px-4 py-3 font-medium">Duration</th>
                <th className="px-4 py-3 font-medium">Started</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {executions?.data.map((exec) => (
                <tr
                  key={exec.id}
                  className="hover:bg-[var(--color-surface-2)]"
                >
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${statusColors[exec.status]}`}
                    >
                      {exec.status}
                    </span>
                    {pendingInputIds.has(exec.id) && (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs bg-yellow-100 text-yellow-800 animate-pulse">
                        Input needed
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {exec.automation_name || "Unknown"}
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                    {exec.triggered_by.display_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                    {exec.duration_ms != null
                      ? formatDuration(exec.duration_ms)
                      : "-"}
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {exec.started_at
                        ? formatDate(exec.started_at)
                        : formatDate(exec.created_at)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/executions/${exec.id}`}
                      className="text-sm text-[var(--color-primary)] hover:underline flex items-center gap-1"
                    >
                      <Terminal className="w-3 h-3" /> View
                    </Link>
                  </td>
                </tr>
              ))}
              {(!executions?.data || executions.data.length === 0) && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-[var(--color-text-muted)]"
                  >
                    No executions found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {executions && executions.meta.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-sm border border-[var(--color-border)] rounded disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-[var(--color-text-muted)]">
            Page {page} of {executions.meta.total_pages}
          </span>
          <button
            onClick={() =>
              setPage((p) =>
                Math.min(executions.meta.total_pages, p + 1)
              )
            }
            disabled={page === executions.meta.total_pages}
            className="px-3 py-1 text-sm border border-[var(--color-border)] rounded disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
