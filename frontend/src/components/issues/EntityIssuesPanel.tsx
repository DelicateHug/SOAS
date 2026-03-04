import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { formatDate, issueStatusColors, issueStatusLabels } from "@/lib/utils";
import { CircleDot, Plus } from "lucide-react";
import type { IssueItem, IssueLinkTargetType } from "@/types/api";

interface Props {
  targetType: IssueLinkTargetType;
  targetId: string;
  targetName: string;
}

export function EntityIssuesPanel({ targetType, targetId, targetName }: Props) {
  const { hasPermission } = useAuthStore();

  const { data: issues, isLoading } = useQuery({
    queryKey: ["entity-issues", targetType, targetId],
    queryFn: () =>
      api.get<IssueItem[]>(`/issues/by-target/${targetType}/${targetId}`),
    enabled: !!targetId,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">
          Issues ({issues?.length ?? 0})
        </h3>
        {hasPermission("issue:create") && (
          <Link
            to={`/issues/new?linkType=${targetType}&linkId=${targetId}&linkName=${encodeURIComponent(targetName)}`}
            className="flex items-center gap-1 text-xs text-[hsl(var(--primary))] hover:underline"
          >
            <Plus className="w-3 h-3" />
            Create Issue
          </Link>
        )}
      </div>

      {isLoading ? (
        <div className="text-center py-4 text-sm">Loading...</div>
      ) : issues?.length === 0 ? (
        <div className="flex flex-col items-center py-8 text-[hsl(var(--muted-foreground))]">
          <CircleDot className="w-8 h-8 mb-2" />
          <p className="text-sm">No issues linked to this item.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {issues?.map((issue) => (
            <Link
              key={issue.id}
              to={`/issues/${issue.id}`}
              className="flex items-center justify-between p-3 border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))] transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">
                    {issue.title}
                  </span>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${
                      issueStatusColors[issue.status] ?? "bg-gray-500/15 text-gray-400"
                    }`}
                  >
                    {issueStatusLabels[issue.status] ?? issue.status}
                  </span>
                </div>
                <div className="flex gap-3 mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                  <span>By {issue.created_by.display_name}</span>
                  {issue.assigned_to && (
                    <span>Assigned: {issue.assigned_to.display_name}</span>
                  )}
                  <span>{formatDate(issue.created_at)}</span>
                </div>
              </div>
              {issue.checklist_total > 0 && (
                <span className="text-xs text-[hsl(var(--muted-foreground))] ml-2 shrink-0">
                  {issue.checklist_checked}/{issue.checklist_total}
                </span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
