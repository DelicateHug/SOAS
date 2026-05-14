import { useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useBranchAwareDetail } from "@/hooks/useBranchAwareDetail";
import { BranchStatusBadge } from "@/components/ui/BranchStatusBadge";
import { api } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/utils";
import { Play, Pencil, Network, Eye } from "lucide-react";
import type { PaginatedResponse, ExecutionItem, AutomationDependencies } from "@/types/api";
import { ProductionGuard } from "@/components/ui/ProductionGuard";
import { VersionManager } from "@/components/VersionManager";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { DocumentationViewer } from "@/components/DocumentationViewer";
import { EntityIssuesPanel } from "@/components/issues/EntityIssuesPanel";
import "@/components/MarkdownEditor.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AutomationDetail {
  id: string;
  name: string;
  description?: string;
  status: string;
  version: number;
  graph_file?: string;
  script_hash?: string;
  parameters: Array<{ name: string; type: string; default?: string }>;
  timeout_seconds: number;
  tags: string[];
  trigger_tags?: string[];
  documentation?: string;
  created_by: { id: string; username: string; display_name: string };
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const executionStatusColors: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800",
  queued: "bg-blue-100 text-blue-800",
  running: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-500",
  timed_out: "bg-orange-100 text-orange-800",
};

const automationStatusColors: Record<string, string> = {
  draft: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  disabled: "bg-gray-100 text-gray-800",
  archived: "bg-gray-100 text-gray-500",
};

const tabs = [
  { key: "overview" as const, label: "Overview" },
  { key: "documentation" as const, label: "Documentation" },
  { key: "history" as const, label: "Execution History" },
  { key: "dependencies" as const, label: "Dependencies" },
  { key: "issues" as const, label: "Issues" },
];

type TabKey = (typeof tabs)[number]["key"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AutomationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [params, setParams] = useState("{}");
  const [docMode, setDocMode] = useState<"view" | "edit">("view");

  // ── Queries ──────────────────────────────────────────────────────────

  const { data: automation, isLoading } = useQuery({
    queryKey: ["automation", id],
    queryFn: () => api.get<AutomationDetail>(`/automations/${id}`),
    enabled: !!id,
  });

  const { hasDraft, draft } = useBranchAwareDetail("automation", id);

  const { data: executions } = useQuery({
    queryKey: ["automation-executions", id],
    queryFn: () =>
      api.get<PaginatedResponse<ExecutionItem>>(
        `/executions?automation_id=${id}&per_page=20`
      ),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      const hasActive = data?.data.some(
        (e) => e.status === "running" || e.status === "queued" || e.status === "pending"
      );
      return hasActive ? 5000 : false;
    },
  });

  const { data: deps } = useQuery({
    queryKey: ["automation-dependencies", id],
    queryFn: () =>
      api.get<AutomationDependencies>(`/automations/${id}/dependencies`),
    enabled: !!id && activeTab === "dependencies",
  });

  // ── Mutations ────────────────────────────────────────────────────────

  const execute = useToastMutation({
    mutationFn: () => {
      let parsedParams = {};
      try {
        parsedParams = JSON.parse(params);
      } catch {
        /* empty */
      }
      return api.post(`/automations/${id}/execute`, { parameters: parsedParams });
    },
    loadingMessage: "Starting execution...",
    successMessage: "Execution started.",
    onSuccess: () => {
      setShowExecuteModal(false);
      setParams("{}");
      queryClient.invalidateQueries({ queryKey: ["automation-executions", id] });
    },
  });

  const saveDocumentation = useToastMutation({
    mutationFn: (documentation: string) =>
      api.patch(`/automations/${id}`, { documentation }),
    loadingMessage: "Saving documentation...",
    successMessage: "Documentation saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automation", id] });
    },
  });

  // ── Handlers ─────────────────────────────────────────────────────────

  const handleDocumentationChange = useCallback(
    (html: string) => {
      saveDocumentation.mutate(html);
    },
    [saveDocumentation]
  );

  // ── Loading / not found ──────────────────────────────────────────────

  if (isLoading) return <div className="text-center py-8">Loading...</div>;
  if (!automation) return <div className="text-center py-8">Automation not found</div>;

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span
              className={`px-2 py-1 rounded text-xs ${automationStatusColors[automation.status]}`}
            >
              {automation.status}
            </span>
            <VersionManager
              entityType="automation"
              entityId={id!}
              currentVersion={automation.version}
              onVersionRestored={() => {
                queryClient.invalidateQueries({ queryKey: ["automation", id] });
              }}
            />
          </div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{automation.name}</h1>
            {hasDraft && draft && (
              <BranchStatusBadge
                branchStatus="modified"
                changeRequest={draft as unknown as import("@/types/api").ChangeRequestItem}
              />
            )}
          </div>
          {automation.description && (
            <p className="mt-2 text-[var(--color-text-muted)]">
              {automation.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ProductionGuard>
            <Link
              to={`/automations/${id}/editor`}
              className="flex items-center gap-2 px-4 py-2 border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)] text-sm"
            >
              <Pencil className="w-4 h-4" /> Edit Graph
            </Link>
          </ProductionGuard>
          <ProductionGuard>
            {automation.status === "active" && (
              <button
                onClick={() => setShowExecuteModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
              >
                <Play className="w-4 h-4" /> Execute
              </button>
            )}
          </ProductionGuard>
        </div>
      </div>

      {/* ── Execute Modal ─────────────────────────────────────────────── */}
      {showExecuteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--color-bg)] rounded-lg p-6 w-full max-w-md border border-[var(--color-border)]">
            <h2 className="text-lg font-semibold mb-4">
              Execute {automation.name}
            </h2>
            <div>
              <label className="block text-sm font-medium mb-1">
                Parameters (JSON)
              </label>
              <textarea
                value={params}
                onChange={(e) => setParams(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md font-mono text-sm"
                rows={5}
              />
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => execute.mutate()}
                disabled={execute.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {execute.isPending ? "Executing..." : "Execute"}
              </button>
              <button
                onClick={() => setShowExecuteModal(false)}
                className="px-4 py-2 border border-[var(--color-border)] rounded-md"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab Navigation ────────────────────────────────────────────── */}
      <div className="border-b border-[var(--color-border)] mb-6">
        <nav className="flex gap-0 -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-[var(--color-primary)] text-[var(--color-text)]"
                  : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-border)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Tab Content ───────────────────────────────────────────────── */}

      {/* Overview */}
      {activeTab === "overview" && (
        <div>
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="border border-[var(--color-border)] rounded-lg p-3">
              <p className="text-xs text-[var(--color-text-muted)]">Timeout</p>
              <p className="font-medium">{automation.timeout_seconds}s</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg p-3">
              <p className="text-xs text-[var(--color-text-muted)]">Graph File</p>
              <p className="font-medium">{automation.graph_file || "None"}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg p-3">
              <p className="text-xs text-[var(--color-text-muted)]">Tags</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {automation.tags.length > 0 ? (
                  automation.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 rounded text-xs bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                    >
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-[var(--color-text-muted)]">None</span>
                )}
              </div>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg p-3">
              <p className="text-xs text-[var(--color-text-muted)]">Trigger Tags</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {automation.trigger_tags && automation.trigger_tags.length > 0 ? (
                  automation.trigger_tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-800"
                    >
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-[var(--color-text-muted)]">None</span>
                )}
              </div>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg p-3">
              <p className="text-xs text-[var(--color-text-muted)]">Created By</p>
              <p className="font-medium">{automation.created_by.display_name}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg p-3">
              <p className="text-xs text-[var(--color-text-muted)]">Created At</p>
              <p className="font-medium">{formatDate(automation.created_at)}</p>
            </div>
            <div className="border border-[var(--color-border)] rounded-lg p-3 col-span-2">
              <p className="text-xs text-[var(--color-text-muted)]">Updated At</p>
              <p className="font-medium">{formatDate(automation.updated_at)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Documentation */}
      {activeTab === "documentation" && (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm text-[var(--color-text-muted)]">
              {docMode === "edit"
                ? "Write documentation for this automation. Changes are saved automatically."
                : "Automation documentation."}
            </p>
            <div className="flex items-center gap-2">
              {docMode === "edit" && saveDocumentation.isPending && (
                <span className="text-xs text-[var(--color-text-muted)]">Saving...</span>
              )}
              <div className="flex rounded-md border border-[var(--color-border)] overflow-hidden">
                <button
                  onClick={() => setDocMode("view")}
                  className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium transition-colors ${
                    docMode === "view"
                      ? "bg-[var(--color-surface-2)] text-[var(--color-text)]"
                      : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)]/50"
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  View
                </button>
                <ProductionGuard>
                  <button
                    onClick={() => setDocMode("edit")}
                    className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium border-l border-[var(--color-border)] transition-colors ${
                      docMode === "edit"
                        ? "bg-[var(--color-surface-2)] text-[var(--color-text)]"
                        : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)]/50"
                    }`}
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    Edit
                  </button>
                </ProductionGuard>
              </div>
            </div>
          </div>

          {docMode === "edit" ? (
            <MarkdownEditor
              content={automation.documentation || ""}
              onChange={handleDocumentationChange}
              placeholder="Start writing documentation for this automation..."
            />
          ) : (
            <DocumentationViewer content={automation.documentation || ""} />
          )}
        </div>
      )}

      {/* Execution History */}
      {activeTab === "history" && (
        <div className="border border-[var(--color-border)] rounded-lg">
          <div className="px-4 py-3 border-b border-[var(--color-border)]">
            <h2 className="font-semibold">Execution History</h2>
          </div>
          <div className="divide-y divide-[var(--color-border)]">
            {executions?.data.map((exec) => (
              <Link
                key={exec.id}
                to={`/executions/${exec.id}`}
                className="px-4 py-3 flex items-center gap-4 hover:bg-[var(--color-surface-2)] transition-colors cursor-pointer block"
              >
                <span
                  className={`px-2 py-0.5 rounded text-xs ${executionStatusColors[exec.status]}`}
                >
                  {exec.status}
                </span>
                <span className="text-sm text-[var(--color-text-muted)]">
                  {exec.triggered_by.display_name}
                </span>
                <span
                  className="text-xs text-[var(--color-text-muted)] font-mono"
                  title={exec.id}
                >
                  {exec.id.slice(0, 8)}
                </span>
                {exec.worker_id && (
                  <span
                    className="text-xs text-[var(--color-text-muted)] font-mono"
                    title={`Worker: ${exec.worker_id}`}
                  >
                    {exec.worker_id}
                  </span>
                )}
                <span className="flex-1" />
                {exec.duration_ms != null && (
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {formatDuration(exec.duration_ms)}
                  </span>
                )}
                <span className="text-xs text-[var(--color-text-muted)]">
                  {formatDate(exec.created_at)}
                </span>
              </Link>
            ))}
            {(!executions?.data || executions.data.length === 0) && (
              <div className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                No executions yet
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dependencies */}
      {activeTab === "dependencies" && (
        <div>
          {/* Uses section */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-3">Uses</h3>
            {!deps || deps.dependencies.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">
                No dependencies
              </p>
            ) : (
              <div className="space-y-2">
                {deps.dependencies.map((dep) => (
                  <Link
                    key={dep.id}
                    to={
                      dep.type === "automation"
                        ? `/automations/${dep.id}`
                        : "/code-library"
                    }
                    className="flex items-center gap-3 px-3 py-2 border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)] transition-colors"
                  >
                    <span className="px-2 py-0.5 rounded text-xs bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
                      {dep.type === "automation" ? "Automation" : "Code Block"}
                    </span>
                    <span className="text-sm">{dep.name || dep.id}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Used By section */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-3">Used By</h3>
            {!deps || deps.dependents.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">
                No dependents
              </p>
            ) : (
              <div className="space-y-2">
                {deps.dependents.map((dep) => (
                  <Link
                    key={dep.id}
                    to={
                      dep.type === "automation"
                        ? `/automations/${dep.id}`
                        : "/code-library"
                    }
                    className="flex items-center gap-3 px-3 py-2 border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)] transition-colors"
                  >
                    <span className="px-2 py-0.5 rounded text-xs bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
                      {dep.type === "automation" ? "Automation" : "Code Block"}
                    </span>
                    <span className="text-sm">{dep.name || dep.id}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* View Full Graph link */}
          <Link
            to={`/automations/${id}/dependencies`}
            className="flex items-center gap-2 text-sm text-[var(--color-primary)] hover:underline"
          >
            <Network className="w-4 h-4" /> View Full Dependency Graph
          </Link>
        </div>
      )}

      {activeTab === "issues" && automation && (
        <EntityIssuesPanel
          targetType="automation"
          targetId={id!}
          targetName={automation.name}
        />
      )}
    </div>
  );
}
