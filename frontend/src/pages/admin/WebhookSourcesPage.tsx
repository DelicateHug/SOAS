import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useBranchAwareList } from "@/hooks/useBranchAwareList";
import { BranchStatusBadge, PendingCreateBadge } from "@/components/ui/BranchStatusBadge";
import { api } from "@/lib/api";
import { Plus, Trash2, X, ChevronDown, ChevronRight, ArrowUp, ArrowDown } from "lucide-react";
import type {
  WebhookSource,
  WebhookSourceListItem,
  SourceAutomation,
  AutomationItem,
  PaginatedResponse,
} from "@/types/api";

export function WebhookSourcesPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [expandedSource, setExpandedSource] = useState<string | null>(null);

  const { items: branchSources, pendingCreates, isLoading } = useBranchAwareList<WebhookSourceListItem, WebhookSourceListItem[]>({
    entityType: "webhook_source",
    queryKey: ["webhook-sources"],
    queryFn: () => api.get<WebhookSourceListItem[]>("/webhook-sources"),
    getId: (s) => s.id,
    getData: (r) => r,
  });

  const { data: automationsData } = useQuery({
    queryKey: ["automations-active"],
    queryFn: () =>
      api.get<PaginatedResponse<AutomationItem>>("/automations?status=active&per_page=100"),
  });
  const automations = automationsData?.data || [];

  const createSource = useToastMutation({
    mutationFn: () =>
      api.post("/webhook-sources", {
        name: formName,
        description: formDescription || null,
      }),
    loadingMessage: "Creating source...",
    successMessage: "Webhook source created.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhook-sources"] });
      setFormName("");
      setFormDescription("");
      setShowCreate(false);
    },
  });

  const deleteSource = useToastMutation({
    mutationFn: (id: string) => api.delete(`/webhook-sources/${id}`),
    loadingMessage: "Deleting source...",
    successMessage: "Webhook source deleted.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhook-sources"] }),
  });

  const linkAutomation = useToastMutation({
    mutationFn: ({
      sourceId,
      automationId,
      runOrder,
    }: {
      sourceId: string;
      automationId: string;
      runOrder: number;
    }) =>
      api.post(`/webhook-sources/${sourceId}/automations`, {
        automation_id: automationId,
        run_order: runOrder,
      }),
    loadingMessage: false,
    successMessage: "Automation linked.",
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["webhook-source", vars.sourceId] });
      queryClient.invalidateQueries({ queryKey: ["webhook-sources"] });
    },
  });

  const unlinkAutomation = useToastMutation({
    mutationFn: ({ sourceId, automationId }: { sourceId: string; automationId: string }) =>
      api.delete(`/webhook-sources/${sourceId}/automations/${automationId}`),
    loadingMessage: false,
    successMessage: "Automation unlinked.",
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["webhook-source", vars.sourceId] });
      queryClient.invalidateQueries({ queryKey: ["webhook-sources"] });
    },
  });

  const updateOrder = useToastMutation({
    mutationFn: ({
      sourceId,
      automationId,
      run_order,
    }: {
      sourceId: string;
      automationId: string;
      run_order: number;
    }) =>
      api.patch(`/webhook-sources/${sourceId}/automations/${automationId}`, {
        run_order,
      }),
    loadingMessage: false,
    successMessage: false,
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["webhook-source", vars.sourceId] });
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Webhook Sources</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Define sources and link automations that run when incidents are created from those sources.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90"
        >
          <Plus className="w-4 h-4" /> Create Source
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="border border-[var(--color-border)] rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium mb-3">New Source</h3>
          <div className="space-y-3">
            <input
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="Source name (e.g. CrowdStrike)"
              className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
            />
            <input
              type="text"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Description (optional)"
              className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
            />
            <div className="flex gap-2">
              <button
                onClick={() => formName.trim() && createSource.mutate()}
                disabled={!formName.trim() || createSource.isPending}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-[#ffffff] disabled:opacity-50"
              >
                Create
              </button>
              <button
                onClick={() => {
                  setShowCreate(false);
                  setFormName("");
                  setFormDescription("");
                }}
                className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)]"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sources list */}
      {isLoading ? (
        <p className="text-[var(--color-text-muted)]">Loading...</p>
      ) : branchSources.length === 0 && pendingCreates.length === 0 ? (
        <div className="text-center py-12 text-[var(--color-text-muted)]">
          <p>No sources created yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {pendingCreates.map((cr) => (
            <div key={cr.id} className="border border-green-500/30 rounded-lg bg-green-500/5 px-4 py-3 flex items-center gap-2">
              <span className="font-medium text-sm">{(cr as unknown as { snapshot?: { name?: string } }).snapshot?.name ?? cr.title}</span>
              <PendingCreateBadge changeRequest={cr} />
            </div>
          ))}
          {branchSources.map(({ item: source, branchStatus, changeRequest }) => (
            <SourceRow
              key={source.id}
              source={source}
              branchStatus={branchStatus}
              branchChangeRequest={changeRequest}
              automations={automations}
              expanded={expandedSource === source.id}
              onToggle={() =>
                setExpandedSource(expandedSource === source.id ? null : source.id)
              }
              onDelete={() => {
                if (confirm(`Delete source "${source.name}"?`)) {
                  deleteSource.mutate(source.id);
                }
              }}
              onLinkAutomation={(automationId, runOrder) =>
                linkAutomation.mutate({ sourceId: source.id, automationId, runOrder })
              }
              onUnlinkAutomation={(automationId) =>
                unlinkAutomation.mutate({ sourceId: source.id, automationId })
              }
              onReorder={(automationId, newOrder) =>
                updateOrder.mutate({ sourceId: source.id, automationId, run_order: newOrder })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceRow({
  source,
  automations,
  expanded,
  onToggle,
  onDelete,
  onLinkAutomation,
  onUnlinkAutomation,
  onReorder,
  branchStatus,
  branchChangeRequest,
}: {
  source: WebhookSourceListItem;
  automations: AutomationItem[];
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onLinkAutomation: (automationId: string, runOrder: number) => void;
  onUnlinkAutomation: (automationId: string) => void;
  onReorder: (automationId: string, newOrder: number) => void;
  branchStatus?: import("@/hooks/useBranchAwareList").BranchStatus;
  branchChangeRequest?: import("@/types/api").ChangeRequestItem;
}) {
  const [linkId, setLinkId] = useState("");

  const moveItem = (sorted: SourceAutomation[], idx: number, direction: -1 | 1) => {
    const newArr = [...sorted];
    const [item] = newArr.splice(idx, 1);
    newArr.splice(idx + direction, 0, item!);
    newArr.forEach((a, i) => {
      if (a.run_order !== i) onReorder(a.automation_id, i);
    });
  };

  // Fetch full source with automations when expanded
  const { data: fullSource } = useQuery({
    queryKey: ["webhook-source", source.id],
    queryFn: () => api.get<WebhookSource>(`/webhook-sources/${source.id}`),
    enabled: expanded,
  });

  const linkedIds = new Set(
    fullSource?.automations.map((a) => a.automation_id) || []
  );
  const availableAutomations = automations.filter((a) => !linkedIds.has(a.id));

  return (
    <div className="border border-[var(--color-border)] rounded-lg">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[var(--color-surface-2)]/50"
        onClick={onToggle}
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 shrink-0" />
        )}
        <div className="flex-1">
          <span className="text-sm font-medium">{source.name}</span>
          {branchStatus && branchStatus !== "unchanged" && branchChangeRequest && (
            <BranchStatusBadge branchStatus={branchStatus} changeRequest={branchChangeRequest} />
          )}
          {source.description && (
            <span className="text-xs text-[var(--color-text-muted)] ml-2">
              {source.description}
            </span>
          )}
        </div>
        <span className="text-xs text-[var(--color-text-muted)]">
          {source.automation_count} automation{source.automation_count !== 1 ? "s" : ""}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="p-1 rounded hover:bg-red-500/20 text-[var(--color-text-muted)] hover:text-red-400"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-[var(--color-border)] px-4 py-3">
          <h4 className="text-xs font-medium text-[var(--color-text-muted)] mb-2 uppercase tracking-wider">
            Linked Automations
          </h4>

          {/* Linked automations list */}
          {fullSource?.automations && fullSource.automations.length > 0 ? (
            <div className="space-y-1 mb-3">
              {[...fullSource.automations]
                .sort((a, b) => a.run_order - b.run_order)
                .map((link, idx, sorted) => (
                  <div
                    key={link.id}
                    className="flex items-center gap-2 py-1.5 px-2 rounded bg-[var(--color-surface-2)]/30"
                  >
                    <div className="flex flex-col">
                      <button
                        disabled={idx === 0}
                        onClick={() => moveItem(sorted, idx, -1)}
                        className="p-0 text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-25"
                      >
                        <ArrowUp className="w-3 h-3" />
                      </button>
                      <button
                        disabled={idx === sorted.length - 1}
                        onClick={() => moveItem(sorted, idx, 1)}
                        className="p-0 text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-25"
                      >
                        <ArrowDown className="w-3 h-3" />
                      </button>
                    </div>
                    <span className="text-sm flex-1">{link.automation_name}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      order: {link.run_order}
                    </span>
                    <button
                      onClick={() => onUnlinkAutomation(link.automation_id)}
                      className="p-0.5 rounded hover:bg-red-500/20 text-[var(--color-text-muted)] hover:text-red-400"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--color-text-muted)] mb-3">
              No automations linked yet.
            </p>
          )}

          {/* Link new automation */}
          {availableAutomations.length > 0 ? (
            <div className="flex gap-2">
              <select
                value={linkId}
                onChange={(e) => setLinkId(e.target.value)}
                className="flex-1 px-2 py-1.5 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
              >
                <option value="">Select automation to link...</option>
                {availableAutomations.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => {
                  if (linkId) {
                    onLinkAutomation(linkId, fullSource?.automations.length ?? 0);
                    setLinkId("");
                  }
                }}
                disabled={!linkId}
                className="px-3 py-1.5 text-sm rounded bg-[var(--color-primary)] text-[#ffffff] disabled:opacity-50"
              >
                Link
              </button>
            </div>
          ) : automations.length === 0 ? (
            <p className="text-xs text-[var(--color-text-muted)] italic">
              No active automations exist. Create an automation and set its status to{" "}
              <span className="font-medium text-[var(--color-text)]">active</span> on
              the{" "}
              <a
                href="/automations"
                className="text-[var(--color-primary)] hover:underline"
              >
                Automations
              </a>{" "}
              page to link it here.
            </p>
          ) : (
            <p className="text-xs text-[var(--color-text-muted)] italic">
              All active automations are already linked to this source.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
