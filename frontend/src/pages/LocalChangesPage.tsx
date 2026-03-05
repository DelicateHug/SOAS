import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  GitBranch,
  Send,
  Undo2,
  Trash2,
  Eye,
  Zap,
  BookOpen,
  Code,
  Variable,
  FileText,
  ShieldCheck,
  ClipboardList,
  Unplug,
  Radio,
  SlidersHorizontal,
  ArrowUpToLine,
} from "lucide-react";
import type {
  ChangeRequestItem,
  ChangeRequestListResponse,
  ChangeRequestStatus,
  PushToDevResult,
} from "@/types/api";

const STATUS_TABS: { label: string; value: ChangeRequestStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Drafts", value: "draft" },
  { label: "Pushed to Dev", value: "pushed_to_dev" },
  { label: "Submitted", value: "submitted" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
  { label: "Applied", value: "applied" },
];

const STATUS_COLORS: Record<ChangeRequestStatus, string> = {
  draft: "bg-zinc-500/20 text-zinc-300",
  pushed_to_dev: "bg-teal-500/20 text-teal-300",
  submitted: "bg-blue-500/20 text-blue-300",
  approved: "bg-green-500/20 text-green-300",
  rejected: "bg-red-500/20 text-red-300",
  applied: "bg-emerald-500/20 text-emerald-300",
  withdrawn: "bg-yellow-500/20 text-yellow-300",
};

const ENTITY_ICONS: Record<string, typeof Zap> = {
  automation: Zap,
  wiki_page: BookOpen,
  code_library: Code,
  soas_variable: Variable,
  incident_variable: FileText,
  role: ShieldCheck,
  form_definition: ClipboardList,
  webhook_source: Unplug,
  webhook: Radio,
  normalization: SlidersHorizontal,
};

const ENTITY_LABELS: Record<string, string> = {
  automation: "Automation",
  wiki_page: "Wiki Page",
  code_library: "Code Library",
  soas_variable: "SOAS Variable",
  incident_variable: "Incident Variable",
  role: "Role",
  form_definition: "Form Definition",
  webhook_source: "Webhook Source",
  webhook: "Webhook",
  normalization: "Normalization",
};

export function LocalChangesPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ChangeRequestStatus | "all">("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["change-request", "mine", statusFilter],
    queryFn: () => {
      const params = new URLSearchParams({ per_page: "100" });
      if (statusFilter !== "all") params.set("status", statusFilter);
      return api.get<ChangeRequestListResponse>(`/change-requests/mine?${params}`);
    },
  });

  const items = data?.data ?? [];

  const submitMutation = useMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/submit`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const withdrawMutation = useMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/withdraw`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/change-requests/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const pushToDevMutation = useMutation({
    mutationFn: async (id: string) => {
      const result = await api.post<PushToDevResult>(
        `/change-requests/${id}/push-to-dev`,
      );
      if (result.status === "conflict") {
        throw new Error(`Merge conflict on: ${result.conflicts.join(", ")}`);
      }
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["entity-version"] });
    },
  });

  const renderDiffSummary = (cr: ChangeRequestItem) => {
    if (!cr.diff_summary) return null;
    return (
      <div className="mt-2 space-y-1">
        {Object.entries(cr.diff_summary).map(([field, diff]) => (
          <div key={field} className="text-xs">
            <span className="text-[hsl(var(--muted-foreground))]">{field}:</span>{" "}
            <span className="text-red-400 line-through">
              {String(diff.old ?? "").substring(0, 80)}
            </span>{" "}
            <span className="text-green-400">
              {String(diff.new ?? "").substring(0, 80)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <GitBranch className="w-6 h-6 text-[hsl(var(--primary))]" />
        <h1 className="text-2xl font-bold">Local Changes</h1>
        <span className="text-sm text-[hsl(var(--muted-foreground))]">
          {data?.total ?? 0} total
        </span>
      </div>

      {/* Status tabs */}
      <div className="flex gap-1 mb-6 border-b border-[hsl(var(--border))]">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              statusFilter === tab.value
                ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
                : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <p className="text-[hsl(var(--muted-foreground))]">Loading...</p>
      )}

      {!isLoading && items.length === 0 && (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <GitBranch className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No change requests found.</p>
          <p className="text-sm mt-1">
            Changes made in production mode are saved as drafts here.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {items.map((cr) => {
          const Icon = ENTITY_ICONS[cr.entity_type] ?? FileText;
          const isExpanded = expandedId === cr.id;

          return (
            <div
              key={cr.id}
              className="border border-[hsl(var(--border))] rounded-lg p-4"
            >
              <div className="flex items-start gap-3">
                <Icon className="w-5 h-5 mt-0.5 text-[hsl(var(--muted-foreground))] shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-medium truncate">{cr.title}</h3>
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[cr.status]}`}
                    >
                      {cr.status}
                    </span>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">
                      {ENTITY_LABELS[cr.entity_type] ?? cr.entity_type}
                    </span>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">
                      {cr.action}
                    </span>
                  </div>

                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    Updated {new Date(cr.updated_at).toLocaleString()}
                    {cr.git_branch && (
                      <span className="ml-2">
                        <GitBranch className="w-3 h-3 inline mr-0.5" />
                        {cr.git_branch}
                        {cr.git_sha && (
                          <span className="ml-1 font-mono">{cr.git_sha.substring(0, 7)}</span>
                        )}
                      </span>
                    )}
                  </p>

                  {cr.review_comment && (
                    <p className="text-sm mt-2 p-2 rounded bg-[hsl(var(--accent))]">
                      <span className="font-medium">Review:</span> {cr.review_comment}
                    </p>
                  )}

                  {isExpanded && renderDiffSummary(cr)}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : cr.id)}
                    className="p-1.5 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
                    title="View details"
                  >
                    <Eye className="w-4 h-4" />
                  </button>

                  {cr.status === "draft" && (
                    <>
                      <button
                        onClick={() => pushToDevMutation.mutate(cr.id)}
                        disabled={pushToDevMutation.isPending}
                        className="p-1.5 rounded hover:bg-teal-500/20 text-teal-400"
                        title="Push to Dev"
                      >
                        <ArrowUpToLine className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => submitMutation.mutate(cr.id)}
                        disabled={submitMutation.isPending}
                        className="p-1.5 rounded hover:bg-blue-500/20 text-blue-400"
                        title="Submit for review"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm("Delete this draft?")) deleteMutation.mutate(cr.id);
                        }}
                        disabled={deleteMutation.isPending}
                        className="p-1.5 rounded hover:bg-red-500/20 text-red-400"
                        title="Delete draft"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}

                  {cr.status === "submitted" && (
                    <button
                      onClick={() => withdrawMutation.mutate(cr.id)}
                      disabled={withdrawMutation.isPending}
                      className="p-1.5 rounded hover:bg-yellow-500/20 text-yellow-400"
                      title="Withdraw submission"
                    >
                      <Undo2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
