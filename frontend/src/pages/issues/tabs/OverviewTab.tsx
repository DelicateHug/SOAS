import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { Plus, Trash2, ExternalLink } from "lucide-react";
import type { IssueDetail } from "@/types/api";

const TARGET_TYPE_LABELS: Record<string, string> = {
  incident: "Incident",
  automation: "Automation",
  scheduled_job: "Job",
  role: "Role",
  code_library_block: "Code Block",
  normalization_rule: "Normalization Rule",
  case: "Incident Group",
  execution_log: "Execution",
};

const TARGET_TYPE_ROUTES: Record<string, string> = {
  incident: "/incidents",
  automation: "/automations",
  scheduled_job: "/executions?tab=jobs",
  role: "/admin/roles",
  code_library_block: "/code-library",
  normalization_rule: "/admin/normalization",
  case: "/cases",
  execution_log: "/executions",
};

interface Props {
  issue: IssueDetail;
  canEdit: boolean;
}

export function OverviewTab({ issue, canEdit }: Props) {
  const queryClient = useQueryClient();
  const [addLinkType, setAddLinkType] = useState<string>("");
  const [addLinkId, setAddLinkId] = useState("");
  const [showAddLink, setShowAddLink] = useState(false);

  const addLink = useToastMutation({
    mutationFn: () =>
      api.post(`/issues/${issue.id}/links`, {
        target_type: addLinkType,
        target_id: addLinkId,
      }),
    loadingMessage: "Adding link...",
    successMessage: "Link added.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", issue.id] });
      setAddLinkType("");
      setAddLinkId("");
      setShowAddLink(false);
    },
  });

  const removeLink = useToastMutation({
    mutationFn: (linkId: string) =>
      api.request(`/issues/${issue.id}/links/${linkId}`, { method: "DELETE" }),
    loadingMessage: "Removing link...",
    successMessage: "Link removed.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", issue.id] });
    },
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Description */}
      <div className="lg:col-span-2">
        <h3 className="text-sm font-semibold mb-2">Description</h3>
        {issue.description ? (
          <p className="text-sm text-[var(--color-text-muted)] whitespace-pre-wrap">
            {issue.description}
          </p>
        ) : (
          <p className="text-sm text-[var(--color-text-muted)] italic">
            No description provided.
          </p>
        )}
      </div>

      {/* Linked Entities */}
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold">Linked Entities ({issue.links.length})</h3>
          {canEdit && (
            <button
              onClick={() => setShowAddLink(!showAddLink)}
              className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline"
            >
              <Plus className="w-3 h-3" />
              Add Link
            </button>
          )}
        </div>

        {showAddLink && (
          <div className="flex gap-2 mb-3 p-3 border border-[var(--color-border)] rounded-md">
            <select
              value={addLinkType}
              onChange={(e) => setAddLinkType(e.target.value)}
              className="px-2 py-1.5 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
            >
              <option value="">Type...</option>
              {Object.entries(TARGET_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <input
              value={addLinkId}
              onChange={(e) => setAddLinkId(e.target.value)}
              placeholder="Entity ID..."
              className="flex-1 px-2 py-1.5 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
            />
            <button
              onClick={() => addLink.mutate()}
              disabled={!addLinkType || !addLinkId || addLink.isPending}
              className="px-3 py-1.5 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm disabled:opacity-50"
            >
              Add
            </button>
          </div>
        )}

        {issue.links.length === 0 ? (
          <p className="text-sm text-[var(--color-text-muted)] italic">
            No linked entities.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {issue.links.map((link) => {
              const route = TARGET_TYPE_ROUTES[link.target_type];
              const href = route?.includes("?")
                ? route
                : `${route}/${link.target_id}`;

              return (
                <div
                  key={link.id}
                  className="flex items-center justify-between p-2 border border-[var(--color-border)] rounded-md"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
                      {TARGET_TYPE_LABELS[link.target_type] ?? link.target_type}
                    </span>
                    <Link
                      to={href}
                      className="text-sm text-[var(--color-primary)] hover:underline flex items-center gap-1"
                    >
                      {link.target_name ?? link.target_id}
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>
                  {canEdit && (
                    <button
                      onClick={() => removeLink.mutate(link.id)}
                      className="p-1 text-[var(--color-text-muted)] hover:text-red-400"
                      title="Remove link"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Details */}
      <div>
        <h3 className="text-sm font-semibold mb-2">Details</h3>
        <dl className="grid grid-cols-2 gap-y-2 text-sm">
          <dt className="text-[var(--color-text-muted)]">Created by</dt>
          <dd>{issue.created_by.display_name}</dd>
          <dt className="text-[var(--color-text-muted)]">Assigned to</dt>
          <dd>{issue.assigned_to?.display_name ?? "Unassigned"}</dd>
          {issue.closed_at && (
            <>
              <dt className="text-[var(--color-text-muted)]">Closed at</dt>
              <dd>{new Date(issue.closed_at).toLocaleString()}</dd>
            </>
          )}
          {issue.graph_annotation && (
            <>
              <dt className="text-[var(--color-text-muted)]">Graph annotation</dt>
              <dd>Version {issue.graph_annotation.automation_version}</dd>
            </>
          )}
        </dl>
      </div>
    </div>
  );
}
