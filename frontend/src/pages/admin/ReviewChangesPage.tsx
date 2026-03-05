import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  GitPullRequest,
  Check,
  X,
  Play,
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
  GitBranch,
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

export function ReviewChangesPage() {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reviewComment, setReviewComment] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["change-request", "pending"],
    queryFn: () =>
      api.get<ChangeRequestListResponse>("/change-requests/pending?per_page=100"),
  });

  const items = data?.data ?? [];

  const approveMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      api.post(`/change-requests/${id}/approve`, { comment: comment || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      setReviewComment("");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      api.post(`/change-requests/${id}/reject`, { comment: comment || null }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      setReviewComment("");
    },
  });

  const applyMutation = useMutation({
    mutationFn: (id: string) => api.post(`/change-requests/${id}/apply`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["change-request"] }),
  });

  const { data: devChanges } = useQuery({
    queryKey: ["branch-versions", "dev-changes"],
    queryFn: () =>
      api.get<DevChangesItem[]>("/branch-versions/dev/changes"),
  });

  const promoteMutation = useMutation({
    mutationFn: () => api.post<PromotionResult>("/branch-versions/promote-to-prod"),
    onSuccess: (result) => {
      if (result.status === "conflict") {
        alert(`Promotion conflict: ${result.conflicts.join(", ")}`);
      }
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["branch-versions"] });
      queryClient.invalidateQueries({ queryKey: ["entity-version"] });
    },
  });

  const devChangeItems = devChanges ?? [];

  const renderDiffSummary = (cr: ChangeRequestItem) => {
    if (!cr.diff_summary) return null;
    return (
      <div className="mt-3 space-y-1 p-3 rounded bg-[hsl(var(--accent))]">
        <p className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-2">
          Changes:
        </p>
        {Object.entries(cr.diff_summary).map(([field, diff]) => (
          <div key={field} className="text-xs">
            <span className="text-[hsl(var(--muted-foreground))]">{field}:</span>{" "}
            <span className="text-red-400 line-through">
              {String(diff.old ?? "").substring(0, 120)}
            </span>{" "}
            <span className="text-green-400">
              {String(diff.new ?? "").substring(0, 120)}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <GitPullRequest className="w-6 h-6 text-[hsl(var(--primary))]" />
        <h1 className="text-2xl font-bold">Review Changes</h1>
        <span className="text-sm text-[hsl(var(--muted-foreground))]">
          {data?.total ?? 0} pending
        </span>
      </div>

      {isLoading && (
        <p className="text-[hsl(var(--muted-foreground))]">Loading...</p>
      )}

      {!isLoading && items.length === 0 && (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <GitPullRequest className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No pending change requests.</p>
          <p className="text-sm mt-1">
            Submitted changes from dev users will appear here for review.
          </p>
        </div>
      )}

      <div className="space-y-4">
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
                    <h3 className="font-medium">{cr.title}</h3>
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-300">
                      {cr.action}
                    </span>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">
                      {ENTITY_LABELS[cr.entity_type] ?? cr.entity_type}
                    </span>
                  </div>

                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    By {cr.creator?.display_name ?? "Unknown"} &middot;{" "}
                    {new Date(cr.created_at).toLocaleString()}
                  </p>

                  {isExpanded && (
                    <>
                      {renderDiffSummary(cr)}

                      <div className="mt-3 flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="Review comment (optional)..."
                          value={reviewComment}
                          onChange={(e) => setReviewComment(e.target.value)}
                          className="flex-1 px-3 py-1.5 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                        />
                        <button
                          onClick={() =>
                            approveMutation.mutate({ id: cr.id, comment: reviewComment })
                          }
                          disabled={approveMutation.isPending}
                          className="px-3 py-1.5 rounded text-sm font-medium bg-green-600 hover:bg-green-700 text-white"
                        >
                          <Check className="w-4 h-4 inline mr-1" />
                          Approve
                        </button>
                        <button
                          onClick={() =>
                            rejectMutation.mutate({ id: cr.id, comment: reviewComment })
                          }
                          disabled={rejectMutation.isPending}
                          className="px-3 py-1.5 rounded text-sm font-medium bg-red-600 hover:bg-red-700 text-white"
                        >
                          <X className="w-4 h-4 inline mr-1" />
                          Reject
                        </button>
                      </div>
                    </>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : cr.id)}
                    className="p-1.5 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
                    title="Review"
                  >
                    <Eye className="w-4 h-4" />
                  </button>

                  {cr.status === "approved" && (
                    <button
                      onClick={() => {
                        if (confirm("Apply this change to production?"))
                          applyMutation.mutate(cr.id);
                      }}
                      disabled={applyMutation.isPending}
                      className="p-1.5 rounded hover:bg-green-500/20 text-green-400"
                      title="Apply to production"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Dev vs Prod section */}
      <div className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <GitBranch className="w-5 h-5 text-teal-400" />
          <h2 className="text-xl font-bold">Dev vs Prod</h2>
          {devChangeItems.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded bg-teal-500/20 text-teal-300">
              {devChangeItems.length} changes
            </span>
          )}
        </div>

        {devChangeItems.length === 0 ? (
          <p className="text-[hsl(var(--muted-foreground))] text-sm">
            Dev and Prod are in sync. No changes to promote.
          </p>
        ) : (
          <>
            <div className="space-y-2 mb-4">
              {devChangeItems.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 text-sm border border-[hsl(var(--border))] rounded px-3 py-2"
                >
                  <span className="font-mono text-xs text-[hsl(var(--muted-foreground))]">
                    {item.file_path}
                  </span>
                </div>
              ))}
            </div>

            <button
              onClick={() => {
                if (confirm("Promote all dev changes to production? This will merge the dev branch into main and apply changes to the live database."))
                  promoteMutation.mutate();
              }}
              disabled={promoteMutation.isPending}
              className="px-4 py-2 rounded text-sm font-medium bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50 flex items-center gap-2"
            >
              <ArrowUpToLine className="w-4 h-4" />
              {promoteMutation.isPending ? "Promoting..." : "Promote All to Prod"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
