import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Clock,
  Plus,
  EllipsisVertical,
  Pencil,
  Trash2,
  Power,
  PowerOff,
  Loader2,
} from "lucide-react";
import { JobFormModal } from "@/pages/jobs/JobFormModal";
import { JobFilters, emptyJobFilters, type JobFilterValues } from "./JobFilters";
import type { PaginatedResponse, ScheduledJobItem } from "@/types/api";

// ---------------------------------------------------------------------------
// Human-readable schedule description
// ---------------------------------------------------------------------------

function describeSchedule(job: ScheduledJobItem): string {
  if (job.schedule_type === "interval" && job.interval_seconds) {
    const s = job.interval_seconds;
    if (s % 86400 === 0)
      return `Every ${s / 86400} day${s / 86400 > 1 ? "s" : ""}`;
    if (s % 3600 === 0)
      return `Every ${s / 3600} hour${s / 3600 > 1 ? "s" : ""}`;
    return `Every ${s / 60} minute${s / 60 > 1 ? "s" : ""}`;
  }

  if (job.schedule_type === "cron" && job.cron_expression) {
    return job.cron_expression;
  }

  if (job.schedule_type === "calendar" && job.calendar_config) {
    const cal = job.calendar_config;
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const parts: string[] = [];

    if (cal.days_of_week.length > 0 && cal.days_of_week.length < 7) {
      if (
        cal.days_of_week.length === 5 &&
        [0, 1, 2, 3, 4].every((d) => cal.days_of_week.includes(d))
      ) {
        parts.push("Weekdays");
      } else {
        parts.push(cal.days_of_week.map((d) => days[d]).join(", "));
      }
    } else if (cal.days_of_week.length === 7) {
      parts.push("Every day");
    }

    if (cal.days_of_month.length > 0) {
      parts.push(`Day ${cal.days_of_month.join(", ")} of month`);
    }

    parts.push(`at ${cal.time}`);
    return parts.join(" ") || "Calendar schedule";
  }

  return "Unknown schedule";
}

// ---------------------------------------------------------------------------
// Action dropdown menu
// ---------------------------------------------------------------------------

function ActionMenu({
  job,
  onEdit,
}: {
  job: ScheduledJobItem;
  onEdit: (j: ScheduledJobItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const queryClient = useQueryClient();

  const toggleMutation = useToastMutation({
    mutationFn: () =>
      api.post(
        `/jobs/${job.id}/${job.is_enabled ? "disable" : "enable"}`,
        {}
      ),
    loadingMessage: `${job.is_enabled ? "Disabling" : "Enabling"} job...`,
    successMessage: `Job ${job.is_enabled ? "disabled" : "enabled"}.`,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setOpen(false);
    },
  });

  const deleteMutation = useToastMutation({
    mutationFn: () => api.delete(`/jobs/${job.id}`),
    loadingMessage: "Deleting job...",
    successMessage: "Job deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setOpen(false);
    },
  });

  return (
    <div className="inline-block">
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (open) {
            setOpen(false);
            setMenuPos(null);
          } else {
            const rect = e.currentTarget.getBoundingClientRect();
            setMenuPos({ top: rect.bottom + 4, left: rect.right });
            setOpen(true);
          }
        }}
        className="p-1 rounded hover:bg-[var(--color-surface-2)]"
      >
        <EllipsisVertical className="w-4 h-4" />
      </button>
      {open && menuPos && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => {
              setOpen(false);
              setMenuPos(null);
            }}
          />
          <div
            className="fixed z-50 w-44 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md shadow-lg py-1"
            style={{ top: menuPos.top, left: menuPos.left - 176 }}
          >
            <button
              onClick={() => {
                onEdit(job);
                setOpen(false);
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)] text-left"
            >
              <Pencil className="w-3.5 h-3.5" /> Edit
            </button>
            <button
              onClick={() => toggleMutation.mutate()}
              disabled={toggleMutation.isPending}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)] text-left disabled:opacity-50"
            >
              {job.is_enabled ? (
                <>
                  <PowerOff className="w-3.5 h-3.5" /> Disable
                </>
              ) : (
                <>
                  <Power className="w-3.5 h-3.5" /> Enable
                </>
              )}
              {toggleMutation.isPending && (
                <Loader2 className="w-3 h-3 animate-spin ml-auto" />
              )}
            </button>
            <div className="border-t border-[var(--color-border)] my-1" />
            <button
              onClick={() => {
                if (confirm("Delete this scheduled job?")) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)] text-left text-red-600 disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
              {deleteMutation.isPending && (
                <Loader2 className="w-3 h-3 animate-spin ml-auto" />
              )}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Jobs tab
// ---------------------------------------------------------------------------

export function JobsTab() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<JobFilterValues>(emptyJobFilters);
  const [editingJob, setEditingJob] = useState<ScheduledJobItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const handleFilterChange = (newFilters: JobFilterValues) => {
    setFilters(newFilters);
    setPage(1);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["jobs", { ...filters, page }],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: "25",
      });
      if (filters.enabled) params.set("enabled", filters.enabled);
      if (filters.automationId)
        params.set("automation_id", filters.automationId);
      return api.get<PaginatedResponse<ScheduledJobItem>>(
        `/jobs?${params}`
      );
    },
  });

  return (
    <div>
      {/* Header with filters + create button */}
      <div className="flex items-start justify-between mb-4">
        <JobFilters filters={filters} onChange={handleFilterChange} />
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 text-sm shrink-0"
        >
          <Plus className="w-4 h-4" />
          Create Job
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : data?.data.length === 0 ? (
        <div className="flex flex-col items-center py-12 text-[var(--color-text-muted)]">
          <Clock className="w-12 h-12 mb-3" />
          <p>No scheduled jobs yet</p>
          <p className="text-sm mt-1">
            Create a job to run automations on a schedule
          </p>
        </div>
      ) : (
        <>
          <div className="border border-[var(--color-border)] rounded-lg overflow-x-auto">
            <table className="w-full min-w-[800px]">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Automation
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Schedule
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Last Run
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Next Run
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Runs
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--color-text-muted)] w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {data?.data.map((job) => (
                  <tr
                    key={job.id}
                    className="hover:bg-[var(--color-surface-2)] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          job.is_enabled
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {job.is_enabled ? "enabled" : "disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium">{job.name}</p>
                      {job.description && (
                        <p className="text-xs text-[var(--color-text-muted)] mt-0.5 truncate max-w-xs">
                          {job.description}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {job.automation_name}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] font-mono">
                        {describeSchedule(job)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {job.last_run_at
                        ? formatDate(job.last_run_at)
                        : "Never"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {job.next_run_at
                        ? formatDate(job.next_run_at)
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {job.run_count}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ActionMenu job={job} onEdit={setEditingJob} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data && data.meta.total_pages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              {Array.from(
                { length: data.meta.total_pages },
                (_, i) => i + 1
              ).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`px-3 py-1 rounded text-sm ${
                    p === page
                      ? "bg-[var(--color-primary)] text-[#ffffff]"
                      : "border border-[var(--color-border)]"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* Create modal */}
      {showCreate && <JobFormModal onClose={() => setShowCreate(false)} />}

      {/* Edit modal */}
      {editingJob && (
        <JobFormModal job={editingJob} onClose={() => setEditingJob(null)} />
      )}
    </div>
  );
}
