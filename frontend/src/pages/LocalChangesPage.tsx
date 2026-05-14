import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToastMutation } from "@/hooks/useToastMutation";
import {
  GitBranch,
  Send,
  Undo2,
  Trash2,
  ChevronDown,
  ChevronRight,
  Search,
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
  MessageSquare,
  Clock,
  CheckCircle2,
  XCircle,
  Circle,
  ArrowUpCircle,
  Filter,
} from "lucide-react";
import type {
  ChangeRequestItem,
  ChangeRequestListResponse,
  ChangeRequestStatus,
} from "@/types/api";

const STATUS_CONFIG: Record<
  ChangeRequestStatus,
  { label: string; color: string; bg: string; icon: typeof Circle }
> = {
  draft: { label: "Draft", color: "text-zinc-400", bg: "bg-zinc-500/20", icon: Circle },
  pushed_to_dev: { label: "On Dev", color: "text-teal-400", bg: "bg-teal-500/20", icon: ArrowUpCircle },
  submitted: { label: "Submitted", color: "text-blue-400", bg: "bg-blue-500/20", icon: Send },
  approved: { label: "Approved", color: "text-green-400", bg: "bg-green-500/20", icon: CheckCircle2 },
  rejected: { label: "Rejected", color: "text-red-400", bg: "bg-red-500/20", icon: XCircle },
  applied: { label: "Applied", color: "text-emerald-400", bg: "bg-emerald-500/20", icon: CheckCircle2 },
  withdrawn: { label: "Withdrawn", color: "text-yellow-400", bg: "bg-yellow-500/20", icon: Undo2 },
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

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  create: { label: "Create", color: "text-green-400" },
  update: { label: "Update", color: "text-blue-400" },
  delete: { label: "Delete", color: "text-red-400" },
};

function DiffView({ diff_summary }: { diff_summary: Record<string, { old: unknown; new: unknown }> }) {
  return (
    <div className="rounded-md border border-[var(--color-border)] overflow-hidden font-mono text-xs">
      {Object.entries(diff_summary).map(([field, diff]) => (
        <div key={field} className="border-b border-[var(--color-border)] last:border-b-0">
          <div className="px-3 py-1.5 bg-[var(--color-surface-2)] text-[var(--color-text-muted)] font-semibold font-sans text-xs">
            {field}
          </div>
          <div className="divide-y divide-[var(--color-border)]">
            {diff.old != null && (
              <div className="px-3 py-1.5 bg-red-500/5 text-red-400 whitespace-pre-wrap break-all">
                <span className="select-none mr-2 opacity-60">-</span>
                {String(diff.old)}
              </div>
            )}
            {diff.new != null && (
              <div className="px-3 py-1.5 bg-green-500/5 text-green-400 whitespace-pre-wrap break-all">
                <span className="select-none mr-2 opacity-60">+</span>
                {String(diff.new)}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: ChangeRequestStatus }) {
  const cfg = STATUS_CONFIG[status];
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}>
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  );
}

function ChangeRequestCard({
  cr,
  isExpanded,
  onToggle,
  onSubmit,
  onWithdraw,
  onDelete,
  isSubmitting,
  isWithdrawing,
  isDeleting,
}: {
  cr: ChangeRequestItem;
  isExpanded: boolean;
  onToggle: () => void;
  onSubmit: (id: string, comment: string) => void;
  onWithdraw: (id: string) => void;
  onDelete: (id: string) => void;
  isSubmitting: boolean;
  isWithdrawing: boolean;
  isDeleting: boolean;
}) {
  const [comment, setComment] = useState("");
  const Icon = ENTITY_ICONS[cr.entity_type] ?? FileText;
  const action = ACTION_LABELS[cr.action] ?? { label: cr.action, color: "text-zinc-400" };

  return (
    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden transition-colors hover:border-[var(--color-border)]/80">
      {/* Header - always visible */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={onToggle}
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-[var(--color-text-muted)] shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-[var(--color-text-muted)] shrink-0" />
        )}
        <Icon className="w-4 h-4 text-[var(--color-text-muted)] shrink-0" />

        <div className="flex-1 min-w-0 flex items-center gap-2">
          <span className="font-medium truncate">{cr.title}</span>
          <StatusBadge status={cr.status} />
          <span className={`text-xs font-medium ${action.color}`}>{action.label}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
          {cr.status === "draft" && (
            <>
              <button
                onClick={() => onSubmit(cr.id, "")}
                disabled={isSubmitting}
                className="px-2.5 py-1 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors"
                title="Submit for review"
              >
                Submit
              </button>
              <button
                onClick={() => { if (confirm("Delete this draft?")) onDelete(cr.id); }}
                disabled={isDeleting}
                className="p-1.5 rounded hover:bg-red-500/20 text-red-400 transition-colors"
                title="Delete draft"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}
          {cr.status === "submitted" && (
            <button
              onClick={() => onWithdraw(cr.id)}
              disabled={isWithdrawing}
              className="px-2.5 py-1 rounded text-xs font-medium bg-yellow-600/80 hover:bg-yellow-600 text-white disabled:opacity-50 transition-colors"
              title="Withdraw"
            >
              Withdraw
            </button>
          )}
        </div>

        <span className="text-xs text-[var(--color-text-muted)] shrink-0 tabular-nums">
          {new Date(cr.updated_at).toLocaleDateString()}
        </span>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-[var(--color-border)] px-4 py-3 space-y-3 bg-[var(--color-surface)]/50">
          {/* Meta info row */}
          <div className="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Updated {new Date(cr.updated_at).toLocaleString()}
            </span>
            <span>
              {ENTITY_LABELS[cr.entity_type] ?? cr.entity_type}
            </span>
            {cr.git_branch && (
              <span className="flex items-center gap-1 font-mono">
                <GitBranch className="w-3 h-3" />
                {cr.git_branch}
                {cr.git_sha && <span className="opacity-60">@{cr.git_sha.substring(0, 7)}</span>}
              </span>
            )}
            {cr.git_pr_url && (
              <a
                href={cr.git_pr_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--color-primary)] hover:underline font-medium"
              >
                View PR
              </a>
            )}
          </div>

          {/* Comments */}
          {(cr.submit_comment || cr.review_comment) && (
            <div className="space-y-2">
              {cr.submit_comment && (
                <div className="flex items-start gap-2 p-2.5 rounded-md bg-blue-500/5 border border-blue-500/10">
                  <MessageSquare className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <span className="text-xs font-medium text-blue-400">Your note:</span>
                    <p className="mt-0.5 text-[var(--color-text)]">{cr.submit_comment}</p>
                  </div>
                </div>
              )}
              {cr.review_comment && (
                <div className="flex items-start gap-2 p-2.5 rounded-md bg-amber-500/5 border border-amber-500/10">
                  <MessageSquare className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <span className="text-xs font-medium text-amber-400">
                      Reviewer ({cr.reviewer?.display_name ?? "Admin"}):
                    </span>
                    <p className="mt-0.5 text-[var(--color-text)]">{cr.review_comment}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Diff */}
          {cr.diff_summary && Object.keys(cr.diff_summary).length > 0 && (
            <DiffView diff_summary={cr.diff_summary} />
          )}

          {/* Submit form for drafts */}
          {cr.status === "draft" && (
            <div className="flex items-center gap-2 pt-1">
              <input
                type="text"
                placeholder="Add a note for reviewers (optional)..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    onSubmit(cr.id, comment);
                    setComment("");
                  }
                }}
                className="flex-1 px-3 py-1.5 text-sm rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
              />
              <button
                onClick={() => { onSubmit(cr.id, comment); setComment(""); }}
                disabled={isSubmitting}
                className="px-4 py-1.5 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                Submit for Review
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function LocalChangesPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ChangeRequestStatus | "all">("all");
  const [entityFilter, setEntityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["change-request", "mine"],
    queryFn: () =>
      api.get<ChangeRequestListResponse>("/change-requests/mine?per_page=100"),
    staleTime: 0,
    refetchInterval: 10000,
  });

  const allItems = data?.data ?? [];

  // Compute filter counts from all items
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allItems.length };
    for (const item of allItems) {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
    }
    return counts;
  }, [allItems]);

  const entityTypes = useMemo(() => {
    const types = new Set(allItems.map((i) => i.entity_type));
    return Array.from(types).sort();
  }, [allItems]);

  // Client-side filtering
  const items = useMemo(() => {
    let filtered = allItems;
    if (statusFilter !== "all") {
      filtered = filtered.filter((i) => i.status === statusFilter);
    }
    if (entityFilter !== "all") {
      filtered = filtered.filter((i) => i.entity_type === entityFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          (ENTITY_LABELS[i.entity_type] ?? i.entity_type).toLowerCase().includes(q),
      );
    }
    return filtered;
  }, [allItems, statusFilter, entityFilter, searchQuery]);

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const submitMutation = useToastMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      api.post(`/change-requests/${id}/submit`, { comment: comment || null }),
    loadingMessage: "Submitting for review...",
    successMessage: "Change request submitted for review.",
    errorMessage: (err: { detail?: string }) => err.detail || "Failed to submit.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const withdrawMutation = useToastMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/withdraw`),
    loadingMessage: "Withdrawing...",
    successMessage: "Submission withdrawn.",
    errorMessage: (err: { detail?: string }) => err.detail || "Failed to withdraw.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const deleteMutation = useToastMutation({
    mutationFn: (id: string) => api.delete(`/change-requests/${id}`),
    loadingMessage: "Deleting...",
    successMessage: "Draft deleted.",
    errorMessage: (err: { detail?: string }) => err.detail || "Failed to delete.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const draftCount = statusCounts["draft"] ?? 0;

  const submitAllDrafts = () => {
    const drafts = allItems.filter((i) => i.status === "draft");
    if (drafts.length === 0) return;
    if (!confirm(`Submit all ${drafts.length} drafts for review?`)) return;
    for (const draft of drafts) {
      submitMutation.mutate({ id: draft.id, comment: "" });
    }
  };

  // Group items by status for overview
  const STATUS_ORDER: ChangeRequestStatus[] = ["draft", "submitted", "approved", "rejected", "applied", "pushed_to_dev", "withdrawn"];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <GitBranch className="w-6 h-6 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold">Local Changes</h1>
          <span className="text-sm text-[var(--color-text-muted)] tabular-nums">
            {allItems.length} total
          </span>
        </div>
        <div className="flex items-center gap-2">
          {draftCount > 1 && (
            <button
              onClick={submitAllDrafts}
              disabled={submitMutation.isPending}
              className="px-3 py-1.5 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors flex items-center gap-1.5"
            >
              <Send className="w-3.5 h-3.5" />
              Submit All Drafts ({draftCount})
            </button>
          )}
        </div>
      </div>

      {/* Search + Filter bar */}
      <div className="flex items-center gap-2 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
          <input
            type="text"
            placeholder="Search changes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`p-2 rounded-md border transition-colors ${
            showFilters || statusFilter !== "all" || entityFilter !== "all"
              ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/5"
              : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
          title="Toggle filters"
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      {/* Filters panel */}
      {showFilters && (
        <div className="mb-4 p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] space-y-3">
          {/* Status pills */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-muted)] mb-1.5 block">Status</label>
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={() => setStatusFilter("all")}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  statusFilter === "all"
                    ? "bg-[var(--color-primary)] text-white"
                    : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                }`}
              >
                All ({statusCounts.all ?? 0})
              </button>
              {STATUS_ORDER.filter((s) => statusCounts[s]).map((s) => {
                const cfg = STATUS_CONFIG[s];
                return (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                      statusFilter === s
                        ? `${cfg.bg} ${cfg.color} ring-1 ring-current`
                        : `bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]`
                    }`}
                  >
                    {cfg.label} ({statusCounts[s]})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Entity type filter */}
          {entityTypes.length > 1 && (
            <div>
              <label className="text-xs font-medium text-[var(--color-text-muted)] mb-1.5 block">Type</label>
              <div className="flex flex-wrap gap-1.5">
                <button
                  onClick={() => setEntityFilter("all")}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                    entityFilter === "all"
                      ? "bg-[var(--color-primary)] text-white"
                      : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  }`}
                >
                  All
                </button>
                {entityTypes.map((t) => (
                  <button
                    key={t}
                    onClick={() => setEntityFilter(t)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                      entityFilter === t
                        ? "bg-[var(--color-primary)]/20 text-[var(--color-primary)] ring-1 ring-[var(--color-primary)]"
                        : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    }`}
                  >
                    {ENTITY_LABELS[t] ?? t}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && items.length === 0 && (
        <div className="text-center py-16 text-[var(--color-text-muted)]">
          <GitBranch className="w-12 h-12 mx-auto mb-3 opacity-20" />
          {allItems.length === 0 ? (
            <>
              <p className="font-medium">No changes yet</p>
              <p className="text-sm mt-1 max-w-sm mx-auto">
                When you make changes in production mode, they'll be saved as drafts here for review before going live.
              </p>
            </>
          ) : (
            <>
              <p className="font-medium">No matching changes</p>
              <p className="text-sm mt-1">Try adjusting your filters or search query.</p>
              <button
                onClick={() => { setStatusFilter("all"); setEntityFilter("all"); setSearchQuery(""); }}
                className="mt-3 text-sm text-[var(--color-primary)] hover:underline"
              >
                Clear all filters
              </button>
            </>
          )}
        </div>
      )}

      {/* Change request list */}
      <div className="space-y-2">
        {items.map((cr) => (
          <ChangeRequestCard
            key={cr.id}
            cr={cr}
            isExpanded={expandedIds.has(cr.id)}
            onToggle={() => toggleExpanded(cr.id)}
            onSubmit={(id, comment) => submitMutation.mutate({ id, comment })}
            onWithdraw={(id) => withdrawMutation.mutate(id)}
            onDelete={(id) => deleteMutation.mutate(id)}
            isSubmitting={submitMutation.isPending}
            isWithdrawing={withdrawMutation.isPending}
            isDeleting={deleteMutation.isPending}
          />
        ))}
      </div>
    </div>
  );
}
