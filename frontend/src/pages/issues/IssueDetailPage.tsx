import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { formatDate, issueStatusColors, issueStatusLabels } from "@/lib/utils";
import { ArrowLeft, Trash2 } from "lucide-react";
import type { IssueDetail, IssueStatus, UserRead } from "@/types/api";
import { OverviewTab } from "./tabs/OverviewTab";
import { NotesTab } from "./tabs/NotesTab";
import { ChecklistTab } from "./tabs/ChecklistTab";

type TabId = "overview" | "notes" | "checklist";

const ALL_STATUSES: IssueStatus[] = ["open", "in_progress", "resolved", "closed", "wont_fix"];

export function IssueDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, hasPermission } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: issue, isLoading } = useQuery({
    queryKey: ["issue", id],
    queryFn: () => api.get<IssueDetail>(`/issues/${id}`),
    enabled: !!id,
  });

  const { data: users } = useQuery({
    queryKey: ["users-brief"],
    queryFn: () => api.get<{ data: UserRead[] }>("/users?per_page=100"),
  });

  const updateIssue = useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      api.patch(`/issues/${id}`, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", id] });
      queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });

  const deleteIssue = useMutation({
    mutationFn: () =>
      api.request(`/issues/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      navigate("/issues");
    },
  });

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (!issue) {
    return (
      <div className="text-center py-8">
        <p className="text-[hsl(var(--muted-foreground))]">Issue not found.</p>
      </div>
    );
  }

  const isCreator = user?.id === issue.created_by.id;
  const canEdit = isCreator || hasPermission("issue:update");
  const canDelete = isCreator || hasPermission("issue:delete");

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: "overview", label: "Overview" },
    { id: "notes", label: "Notes", count: issue.note_count },
    {
      id: "checklist",
      label: "Checklist",
      count: issue.checklist_total > 0
        ? undefined
        : undefined,
    },
  ];

  return (
    <div>
      {/* Header */}
      <button
        onClick={() => navigate("/issues")}
        className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Issues
      </button>

      <div className="flex items-start justify-between mb-6">
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{issue.title}</h1>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-[hsl(var(--muted-foreground))]">
            <span>Created by {issue.created_by.display_name}</span>
            <span>{formatDate(issue.created_at)}</span>
            {issue.checklist_total > 0 && (
              <span>Checklist: {issue.checklist_checked}/{issue.checklist_total}</span>
            )}
          </div>
        </div>

        {canDelete && (
          <div className="relative">
            {confirmDelete ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-red-400">Confirm?</span>
                <button
                  onClick={() => deleteIssue.mutate()}
                  className="px-2 py-1 text-xs bg-red-500 text-white rounded"
                >
                  Delete
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="px-2 py-1 text-xs border border-[hsl(var(--border))] rounded"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmDelete(true)}
                className="p-2 text-[hsl(var(--muted-foreground))] hover:text-red-400"
                title="Delete issue"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Status and assignment controls */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-4 border border-[hsl(var(--border))] rounded-lg">
        <div>
          <label className="block text-xs text-[hsl(var(--muted-foreground))] mb-1">Status</label>
          {canEdit ? (
            <select
              value={issue.status}
              onChange={(e) => updateIssue.mutate({ status: e.target.value })}
              className="px-2 py-1.5 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              {ALL_STATUSES.map((s) => (
                <option key={s} value={s}>{issueStatusLabels[s]}</option>
              ))}
            </select>
          ) : (
            <span className={`text-xs px-2 py-0.5 rounded ${issueStatusColors[issue.status]}`}>
              {issueStatusLabels[issue.status]}
            </span>
          )}
        </div>

        <div>
          <label className="block text-xs text-[hsl(var(--muted-foreground))] mb-1">Assigned to</label>
          {canEdit ? (
            <select
              value={issue.assigned_to?.id ?? ""}
              onChange={(e) =>
                updateIssue.mutate({
                  assigned_to: e.target.value || null,
                })
              }
              className="px-2 py-1.5 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value="">Unassigned</option>
              {users?.data?.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.display_name}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-sm">{issue.assigned_to?.display_name ?? "Unassigned"}</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-[hsl(var(--border))] mb-6">
        <div className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
                  : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              }`}
            >
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <span className="ml-1 text-xs text-[hsl(var(--muted-foreground))]">
                  ({tab.count})
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <OverviewTab issue={issue} canEdit={canEdit} />
      )}
      {activeTab === "notes" && (
        <NotesTab issueId={issue.id} issueCreatorId={issue.created_by.id} />
      )}
      {activeTab === "checklist" && (
        <ChecklistTab issueId={issue.id} issueCreatorId={issue.created_by.id} />
      )}
    </div>
  );
}
