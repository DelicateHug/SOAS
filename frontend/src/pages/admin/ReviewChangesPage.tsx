import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useToast } from "@/stores/toastStore";
import { api } from "@/lib/api";
import { UserAvatar } from "@/components/ui/UserAvatar";
import {
  GitPullRequest,
  Check,
  X,
  Play,
  ChevronDown,
  ChevronRight,
  Search,
  Filter,
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
  GitBranch,
  MessageSquare,
  Clock,
  Users,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import type {
  ChangeRequestItem,
  ChangeRequestListResponse,
  DevChangesItem,
  PromotionResult,
} from "@/types/api";

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

const ACTION_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  create: { label: "Create", color: "text-green-400", bg: "bg-green-500/15" },
  update: { label: "Update", color: "text-blue-400", bg: "bg-blue-500/15" },
  delete: { label: "Delete", color: "text-red-400", bg: "bg-red-500/15" },
};

function DiffView({ diff_summary }: { diff_summary: Record<string, { old: unknown; new: unknown }> }) {
  const [collapsedFields, setCollapsedFields] = useState<Set<string>>(new Set());
  const toggleField = (field: string) => {
    setCollapsedFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  };

  return (
    <div className="rounded-md border border-[hsl(var(--border))] overflow-hidden font-mono text-xs">
      {Object.entries(diff_summary).map(([field, diff]) => {
        const isCollapsed = collapsedFields.has(field);
        const oldStr = String(diff.old ?? "");
        const newStr = String(diff.new ?? "");
        const isLong = oldStr.length > 200 || newStr.length > 200;

        return (
          <div key={field} className="border-b border-[hsl(var(--border))] last:border-b-0">
            <div
              className="px-3 py-1.5 bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] font-semibold font-sans text-xs flex items-center gap-1.5 cursor-pointer select-none"
              onClick={() => isLong && toggleField(field)}
            >
              {isLong && (
                isCollapsed
                  ? <ChevronRight className="w-3 h-3" />
                  : <ChevronDown className="w-3 h-3" />
              )}
              {field}
              {isLong && isCollapsed && (
                <span className="font-normal opacity-60 ml-1">
                  ({oldStr.length} → {newStr.length} chars)
                </span>
              )}
            </div>
            {!isCollapsed && (
              <div className="divide-y divide-[hsl(var(--border))]">
                {diff.old != null && (
                  <div className="px-3 py-1.5 bg-red-500/5 text-red-400 whitespace-pre-wrap break-all">
                    <span className="select-none mr-2 opacity-60">-</span>
                    {oldStr}
                  </div>
                )}
                {diff.new != null && (
                  <div className="px-3 py-1.5 bg-green-500/5 text-green-400 whitespace-pre-wrap break-all">
                    <span className="select-none mr-2 opacity-60">+</span>
                    {newStr}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ReviewCard({
  cr,
  isExpanded,
  onToggle,
  onApprove,
  onReject,
  onApply,
  isApproving,
  isRejecting,
  isApplying,
}: {
  cr: ChangeRequestItem;
  isExpanded: boolean;
  onToggle: () => void;
  onApprove: (id: string, comment: string) => void;
  onReject: (id: string, comment: string) => void;
  onApply: (id: string) => void;
  isApproving: boolean;
  isRejecting: boolean;
  isApplying: boolean;
}) {
  const [comment, setComment] = useState("");
  const Icon = ENTITY_ICONS[cr.entity_type] ?? FileText;
  const action = ACTION_LABELS[cr.action] ?? { label: cr.action, color: "text-zinc-400", bg: "bg-zinc-500/15" };
  const creatorName = cr.creator?.display_name ?? "Unknown";

  return (
    <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none hover:bg-[hsl(var(--accent))]/30 transition-colors"
        onClick={onToggle}
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-[hsl(var(--muted-foreground))] shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-[hsl(var(--muted-foreground))] shrink-0" />
        )}

        <Icon className="w-4 h-4 text-[hsl(var(--muted-foreground))] shrink-0" />

        <div className="flex-1 min-w-0 flex items-center gap-2">
          <span className="font-medium truncate">{cr.title}</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${action.bg} ${action.color}`}>
            {action.label}
          </span>
          <span className="text-xs text-[hsl(var(--muted-foreground))]">
            {ENTITY_LABELS[cr.entity_type] ?? cr.entity_type}
          </span>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1.5" title={creatorName}>
            <UserAvatar displayName={creatorName} size="sm" />
            <span className="text-xs text-[hsl(var(--muted-foreground))]">{creatorName}</span>
          </div>
          <span className="text-xs text-[hsl(var(--muted-foreground))] tabular-nums">
            {new Date(cr.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>

      {/* Expanded review panel */}
      {isExpanded && (
        <div className="border-t border-[hsl(var(--border))] bg-[hsl(var(--card))]/50">
          {/* Details */}
          <div className="px-4 py-3 space-y-3">
            {/* Meta */}
            <div className="flex items-center gap-4 text-xs text-[hsl(var(--muted-foreground))]">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                Created {new Date(cr.created_at).toLocaleString()}
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
                  className="text-[hsl(var(--primary))] hover:underline font-medium"
                >
                  View PR
                </a>
              )}
            </div>

            {/* Submitter note */}
            {cr.submit_comment && (
              <div className="flex items-start gap-2 p-3 rounded-md bg-blue-500/5 border border-blue-500/10">
                <MessageSquare className="w-3.5 h-3.5 text-blue-400 mt-0.5 shrink-0" />
                <div className="text-sm">
                  <span className="text-xs font-medium text-blue-400">
                    {creatorName}'s note:
                  </span>
                  <p className="mt-0.5 text-[hsl(var(--foreground))]">{cr.submit_comment}</p>
                </div>
              </div>
            )}

            {/* Diff */}
            {cr.diff_summary && Object.keys(cr.diff_summary).length > 0 && (
              <div>
                <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1.5 block">
                  Changes ({Object.keys(cr.diff_summary).length} field{Object.keys(cr.diff_summary).length !== 1 ? "s" : ""})
                </label>
                <DiffView diff_summary={cr.diff_summary} />
              </div>
            )}
          </div>

          {/* Review actions */}
          {cr.status === "submitted" && (
            <div className="border-t border-[hsl(var(--border))] px-4 py-3 space-y-2">
              <textarea
                placeholder="Add a review comment (optional)..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] resize-none focus:outline-none focus:ring-1 focus:ring-[hsl(var(--primary))]"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={() => { onApprove(cr.id, comment); setComment(""); }}
                  disabled={isApproving}
                  className="px-4 py-2 rounded-md text-sm font-medium bg-green-600 hover:bg-green-700 text-white disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  <Check className="w-4 h-4" />
                  {isApproving ? "Applying..." : "Approve & Apply"}
                </button>
                <button
                  onClick={() => { onReject(cr.id, comment); setComment(""); }}
                  disabled={isRejecting}
                  className="px-4 py-2 rounded-md text-sm font-medium bg-red-600 hover:bg-red-700 text-white disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  <X className="w-4 h-4" />
                  Reject
                </button>
              </div>
            </div>
          )}

          {cr.status === "approved" && (
            <div className="border-t border-[hsl(var(--border))] px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="text-sm text-green-400 font-medium flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  Approved
                  {cr.reviewer && <span className="text-[hsl(var(--muted-foreground))] font-normal">by {cr.reviewer.display_name}</span>}
                </span>
                <button
                  onClick={() => onApply(cr.id)}
                  disabled={isApplying}
                  className="px-3 py-1.5 rounded-md text-sm font-medium bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5" />
                  {isApplying ? "Applying..." : "Re-apply"}
                </button>
              </div>
              {cr.review_comment && (
                <div className="mt-2 flex items-start gap-2 p-2.5 rounded-md bg-amber-500/5 border border-amber-500/10">
                  <MessageSquare className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <span className="text-xs font-medium text-amber-400">Review comment:</span>
                    <p className="mt-0.5 text-[hsl(var(--foreground))]">{cr.review_comment}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ReviewChangesPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<"reviews" | "dev-prod">("reviews");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [entityFilter, setEntityFilter] = useState<string>("all");
  const [creatorFilter, setCreatorFilter] = useState<string>("all");
  const [showFilters, setShowFilters] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["change-request", "pending"],
    queryFn: () =>
      api.get<ChangeRequestListResponse>("/change-requests/pending?per_page=200"),
    refetchInterval: 10000,
  });

  const allItems = data?.data ?? [];

  // Derive filter options
  const entityTypes = useMemo(
    () => Array.from(new Set(allItems.map((i) => i.entity_type))).sort(),
    [allItems],
  );

  const creators = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of allItems) {
      if (item.creator) map.set(item.created_by, item.creator.display_name);
    }
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [allItems]);

  // Filter
  const items = useMemo(() => {
    let filtered = allItems;
    if (entityFilter !== "all") {
      filtered = filtered.filter((i) => i.entity_type === entityFilter);
    }
    if (creatorFilter !== "all") {
      filtered = filtered.filter((i) => i.created_by === creatorFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          (i.creator?.display_name ?? "").toLowerCase().includes(q) ||
          (ENTITY_LABELS[i.entity_type] ?? i.entity_type).toLowerCase().includes(q),
      );
    }
    return filtered;
  }, [allItems, entityFilter, creatorFilter, searchQuery]);

  const hasActiveFilters = entityFilter !== "all" || creatorFilter !== "all" || searchQuery !== "";

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const approveMutation = useToastMutation({
    mutationFn: async ({ id, comment }: { id: string; comment: string }) => {
      await api.post(`/change-requests/${id}/approve`, { comment: comment || null });
      await api.post(`/change-requests/${id}/apply`, { comment: comment || null });
    },
    loadingMessage: "Approving and applying...",
    successMessage: "Change approved and applied.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["entity-version"] });
    },
  });

  const rejectMutation = useToastMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      api.post(`/change-requests/${id}/reject`, { comment: comment || null }),
    loadingMessage: "Rejecting...",
    successMessage: "Change rejected.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const applyMutation = useToastMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/apply`),
    loadingMessage: "Applying...",
    successMessage: "Change applied.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const { data: devChanges } = useQuery({
    queryKey: ["branch-versions", "dev-changes"],
    queryFn: () => api.get<DevChangesItem[]>("/branch-versions/dev/changes"),
  });

  const promoteMutation = useToastMutation({
    mutationFn: () => api.post<PromotionResult>("/branch-versions/promote-to-prod"),
    loadingMessage: "Promoting to production...",
    successMessage: "Promotion complete.",
    onSuccess: (result) => {
      if (result.status === "conflict") {
        toast("error", `Promotion conflict: ${result.conflicts.join(", ")}`);
      }
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["branch-versions"] });
      queryClient.invalidateQueries({ queryKey: ["entity-version"] });
    },
  });

  const devChangeItems = devChanges ?? [];

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <GitPullRequest className="w-6 h-6 text-[hsl(var(--primary))]" />
        <h1 className="text-2xl font-bold">Review Changes</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-[hsl(var(--border))]">
        <button
          onClick={() => setActiveTab("reviews")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "reviews"
              ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
              : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
          }`}
        >
          <GitPullRequest className="w-4 h-4" />
          Pending Reviews
          {allItems.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/20 text-blue-400 tabular-nums">
              {allItems.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("dev-prod")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            activeTab === "dev-prod"
              ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
              : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
          }`}
        >
          <GitBranch className="w-4 h-4" />
          Dev vs Prod
          {devChangeItems.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-teal-500/20 text-teal-300 tabular-nums">
              {devChangeItems.length}
            </span>
          )}
        </button>
      </div>

      {/* === Pending Reviews Tab === */}
      {activeTab === "reviews" && (
        <>
          {/* Search + Filters */}
          <div className="flex items-center gap-2 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
              <input
                type="text"
                placeholder="Search by title, author, or type..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--background))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--primary))]"
              />
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-md border transition-colors ${
                showFilters || hasActiveFilters
                  ? "border-[hsl(var(--primary))] text-[hsl(var(--primary))] bg-[hsl(var(--primary))]/5"
                  : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              }`}
              title="Toggle filters"
            >
              <Filter className="w-4 h-4" />
            </button>
          </div>

          {/* Filter panel */}
          {showFilters && (
            <div className="mb-4 p-3 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))] space-y-3">
              {entityTypes.length > 1 && (
                <div>
                  <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1.5 block">Type</label>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setEntityFilter("all")}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        entityFilter === "all"
                          ? "bg-[hsl(var(--primary))] text-white"
                          : "bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
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
                            ? "bg-[hsl(var(--primary))]/20 text-[hsl(var(--primary))] ring-1 ring-[hsl(var(--primary))]"
                            : "bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                        }`}
                      >
                        {ENTITY_LABELS[t] ?? t}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {creators.length > 1 && (
                <div>
                  <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1.5 flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    Submitted by
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setCreatorFilter("all")}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                        creatorFilter === "all"
                          ? "bg-[hsl(var(--primary))] text-white"
                          : "bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                      }`}
                    >
                      All
                    </button>
                    {creators.map(([id, name]) => (
                      <button
                        key={id}
                        onClick={() => setCreatorFilter(id)}
                        className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors flex items-center gap-1 ${
                          creatorFilter === id
                            ? "bg-[hsl(var(--primary))]/20 text-[hsl(var(--primary))] ring-1 ring-[hsl(var(--primary))]"
                            : "bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                        }`}
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {hasActiveFilters && (
                <button
                  onClick={() => { setEntityFilter("all"); setCreatorFilter("all"); setSearchQuery(""); }}
                  className="text-xs text-[hsl(var(--primary))] hover:underline"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}

          {/* Loading */}
          {isLoading && (
            <div className="flex items-center justify-center py-16">
              <div className="w-6 h-6 border-2 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {/* Empty state */}
          {!isLoading && items.length === 0 && (
            <div className="text-center py-16 text-[hsl(var(--muted-foreground))]">
              <GitPullRequest className="w-12 h-12 mx-auto mb-3 opacity-20" />
              {allItems.length === 0 ? (
                <>
                  <p className="font-medium">No pending reviews</p>
                  <p className="text-sm mt-1 max-w-sm mx-auto">
                    When users submit changes for review, they'll appear here for approval.
                  </p>
                </>
              ) : (
                <>
                  <p className="font-medium">No matching changes</p>
                  <p className="text-sm mt-1">Try adjusting your filters.</p>
                  <button
                    onClick={() => { setEntityFilter("all"); setCreatorFilter("all"); setSearchQuery(""); }}
                    className="mt-3 text-sm text-[hsl(var(--primary))] hover:underline"
                  >
                    Clear all filters
                  </button>
                </>
              )}
            </div>
          )}

          {/* Pending reviews list */}
          <div className="space-y-2">
            {items.map((cr) => (
              <ReviewCard
                key={cr.id}
                cr={cr}
                isExpanded={expandedIds.has(cr.id)}
                onToggle={() => toggleExpanded(cr.id)}
                onApprove={(id, comment) => approveMutation.mutate({ id, comment })}
                onReject={(id, comment) => rejectMutation.mutate({ id, comment })}
                onApply={(id) => applyMutation.mutate(id)}
                isApproving={approveMutation.isPending}
                isRejecting={rejectMutation.isPending}
                isApplying={applyMutation.isPending}
              />
            ))}
          </div>
        </>
      )}

      {/* === Dev vs Prod Tab === */}
      {activeTab === "dev-prod" && (
        <>
          {devChangeItems.length === 0 ? (
            <div className="text-center py-16 text-[hsl(var(--muted-foreground))]">
              <CheckCircle2 className="w-10 h-10 mx-auto mb-3 opacity-20" />
              <p className="font-medium">Dev and Prod are in sync</p>
              <p className="text-sm mt-1">No changes to promote.</p>
            </div>
          ) : (
            <>
              <div className="rounded-lg border border-[hsl(var(--border))] overflow-hidden mb-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--accent))]/50">
                      <th className="text-left px-3 py-2 text-xs font-medium text-[hsl(var(--muted-foreground))]">File</th>
                      <th className="text-left px-3 py-2 text-xs font-medium text-[hsl(var(--muted-foreground))]">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {devChangeItems.map((item, i) => {
                      const EntIcon = ENTITY_ICONS[item.entity_type ?? ""] ?? FileText;
                      return (
                        <tr key={i} className="border-b border-[hsl(var(--border))] last:border-b-0">
                          <td className="px-3 py-2 font-mono text-xs text-[hsl(var(--foreground))]">
                            {item.file_path}
                          </td>
                          <td className="px-3 py-2">
                            {item.entity_type && (
                              <span className="inline-flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))]">
                                <EntIcon className="w-3 h-3" />
                                {ENTITY_LABELS[item.entity_type] ?? item.entity_type}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    if (confirm("Promote all dev changes to production? This will merge the dev branch into main and apply changes to the live database."))
                      promoteMutation.mutate();
                  }}
                  disabled={promoteMutation.isPending}
                  className="px-4 py-2 rounded-md text-sm font-medium bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50 transition-colors flex items-center gap-2"
                >
                  <ArrowUpToLine className="w-4 h-4" />
                  {promoteMutation.isPending ? "Promoting..." : "Promote All to Prod"}
                </button>
                <span className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  Merges dev branch into main and applies to the live database
                </span>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
