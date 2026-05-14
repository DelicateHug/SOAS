import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useBranchAwareList } from "@/hooks/useBranchAwareList";
import { BranchStatusBadge, PendingCreateBadge } from "@/components/ui/BranchStatusBadge";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { TagInput } from "@/components/ui/TagInput";
import {
  Zap,
  Upload,
  Plus,
  EllipsisVertical,
  Pencil,
  Shield,
  Code,
  Power,
  PowerOff,
  Trash2,
  X,
  Loader2,
} from "lucide-react";
import { PermissionsPanel } from "@/components/graph-editor/PermissionsPanel";
import { ProductionGuard } from "@/components/ui/ProductionGuard";
import type { PaginatedResponse, AutomationItem, AutomationStatus } from "@/types/api";
import { useTeamStore } from "@/stores/teamStore";

const statusColors: Record<string, string> = {
  draft: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  disabled: "bg-gray-100 text-gray-800",
  archived: "bg-gray-100 text-gray-500",
};

const allStatuses: AutomationStatus[] = ["draft", "active", "disabled", "archived"];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function AutomationListPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState({ status: "", page: 1 });
  const activeTeamId = useTeamStore((s) => s.activeTeamId);
  const [editingAutomation, setEditingAutomation] = useState<AutomationItem | null>(null);
  const [permissionsAutomationId, setPermissionsAutomationId] = useState<string | null>(null);
  const [deletingAutomationId, setDeletingAutomationId] = useState<string | null>(null);

  const deleteMutation = useToastMutation({
    mutationFn: (id: string) => api.request(`/automations/${id}`, { method: "DELETE" }),
    loadingMessage: "Deleting automation...",
    successMessage: "Automation deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations"] });
      setDeletingAutomationId(null);
    },
  });

  const { items: branchItems, pendingCreates, raw: data, isLoading } = useBranchAwareList<AutomationItem, PaginatedResponse<AutomationItem>>({
    entityType: "automation",
    queryKey: ["automations", filters, activeTeamId],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      params.set("team_id", activeTeamId!);
      params.set("page", String(filters.page));
      params.set("per_page", "25");
      return api.get<PaginatedResponse<AutomationItem>>(`/automations?${params}`);
    },
    getId: (a) => a.id,
    getData: (r) => r.data,
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Automations</h1>
        <ProductionGuard>
          <div className="flex items-center gap-2">
            <Link
              to="/automations/new"
              className="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 text-sm"
            >
              <Plus className="w-4 h-4" />
              Create New
            </Link>
            <Link
              to="/automations/upload"
              className="flex items-center gap-2 px-4 py-2 border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)] text-sm"
            >
              <Upload className="w-4 h-4" />
              Upload .vpy
            </Link>
          </div>
        </ProductionGuard>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm bg-[var(--color-bg)]"
        >
          <option value="">All Statuses</option>
          {allStatuses.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : branchItems.length === 0 && pendingCreates.length === 0 ? (
        <div className="flex flex-col items-center py-12 text-[var(--color-text-muted)]">
          <Zap className="w-12 h-12 mb-3" />
          <p>No automations yet</p>
          <p className="text-sm mt-1">Upload a .vpy file to get started</p>
        </div>
      ) : (
        <>
          <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Version
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Tags
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Created By
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-muted)]">
                    Updated
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-[var(--color-text-muted)] w-16" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {pendingCreates.map((cr) => (
                  <tr key={cr.id} className="bg-green-500/5">
                    <td className="px-4 py-3">
                      <PendingCreateBadge changeRequest={cr} />
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">
                      {(cr as unknown as { snapshot?: { name?: string } }).snapshot?.name ?? cr.title}
                    </td>
                    <td className="px-4 py-3">-</td>
                    <td className="px-4 py-3">-</td>
                    <td className="px-4 py-3">-</td>
                    <td className="px-4 py-3">-</td>
                    <td className="px-4 py-3" />
                  </tr>
                ))}
                {branchItems.map(({ item: automation, branchStatus, changeRequest }) => (
                  <tr
                    key={automation.id}
                    className={`hover:bg-[var(--color-surface-2)] transition-colors ${branchStatus === "pending_delete" ? "opacity-50 line-through" : ""}`}
                  >
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[automation.status]}`}
                        >
                          {automation.status}
                        </span>
                        <BranchStatusBadge branchStatus={branchStatus} changeRequest={changeRequest} />
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/automations/${automation.id}`}
                        className="text-sm font-medium text-[var(--color-primary)] hover:underline"
                      >
                        {automation.name}
                      </Link>
                      {automation.description && (
                        <p className="text-xs text-[var(--color-text-muted)] mt-0.5 truncate max-w-xs">
                          {automation.description}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      v{automation.version}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {automation.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                          >
                            {tag}
                          </span>
                        ))}
                        {automation.tags.length > 3 && (
                          <span className="text-xs text-[var(--color-text-muted)]">
                            +{automation.tags.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {automation.created_by?.display_name || "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--color-text-muted)]">
                      {formatDate(automation.updated_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <ProductionGuard>
                        <ActionMenu
                          automation={automation}
                          onEditConfig={setEditingAutomation}
                          onPermissions={setPermissionsAutomationId}
                          onDelete={setDeletingAutomationId}
                        />
                      </ProductionGuard>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data && data.meta.total_pages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              {Array.from({ length: data.meta.total_pages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => setFilters({ ...filters, page })}
                  className={`px-3 py-1 rounded text-sm ${
                    page === filters.page
                      ? "bg-[var(--color-primary)] text-[#ffffff]"
                      : "border border-[var(--color-border)]"
                  }`}
                >
                  {page}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* Edit Configuration Modal */}
      {editingAutomation && (
        <EditConfigurationModal
          automation={editingAutomation}
          onClose={() => setEditingAutomation(null)}
        />
      )}

      {/* Permissions Modal */}
      {permissionsAutomationId && (
        <PermissionsPanel
          automationId={permissionsAutomationId}
          onClose={() => setPermissionsAutomationId(null)}
        />
      )}

      {/* Delete Confirmation */}
      {deletingAutomationId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl w-[400px] p-6">
            <h2 className="text-sm font-semibold mb-2">Delete Automation</h2>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Are you sure you want to delete this automation? This action cannot be undone.
            </p>
            {deleteMutation.isError && (
              <p className="text-xs text-red-500 mb-3">Failed to delete. Please try again.</p>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeletingAutomationId(null)}
                className="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deletingAutomationId)}
                disabled={deleteMutation.isPending}
                className="px-3 py-1.5 text-xs rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Action dropdown menu
// ---------------------------------------------------------------------------

function ActionMenu({
  automation,
  onEditConfig,
  onPermissions,
  onDelete,
}: {
  automation: AutomationItem;
  onEditConfig: (a: AutomationItem) => void;
  onPermissions: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const open = pos !== null;

  const toggle = useCallback(() => {
    if (open) {
      setPos(null);
    } else if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setPos({ x: rect.right, y: rect.bottom + 4 });
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        menuRef.current && !menuRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setPos(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        onClick={(e) => {
          e.stopPropagation();
          toggle();
        }}
        className="p-1 rounded hover:bg-[var(--color-surface-2)]"
      >
        <EllipsisVertical className="w-4 h-4" />
      </button>
      {open &&
        createPortal(
          <div
            ref={menuRef}
            className="fixed z-[9999] w-48 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md shadow-lg py-1"
            style={{ top: pos.y, left: pos.x, transform: "translateX(-100%)" }}
          >
            <button
              onClick={() => {
                onEditConfig(automation);
                setPos(null);
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)] text-left"
            >
              <Pencil className="w-3.5 h-3.5" /> Edit Configuration
            </button>
            <button
              onClick={() => {
                onPermissions(automation.id);
                setPos(null);
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)] text-left"
            >
              <Shield className="w-3.5 h-3.5" /> Permissions
            </button>
            <Link
              to={`/automations/${automation.id}/editor`}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)]"
              onClick={() => setPos(null)}
            >
              <Code className="w-3.5 h-3.5" /> Open Editor
            </Link>
            {automation.status !== "archived" && (
              <>
                <div className="border-t border-[var(--color-border)] my-1" />
                <ToggleStatusButton automation={automation} onDone={() => setPos(null)} />
              </>
            )}
            <div className="border-t border-[var(--color-border)] my-1" />
            <button
              onClick={() => {
                onDelete(automation.id);
                setPos(null);
              }}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-red-500/10 text-red-500 text-left"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </div>,
          document.body
        )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Status toggle button (inside action menu)
// ---------------------------------------------------------------------------

function ToggleStatusButton({
  automation,
  onDone,
}: {
  automation: AutomationItem;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const isActive = automation.status === "active";
  const newStatus = isActive ? "disabled" : "active";

  const toggle = useToastMutation({
    mutationFn: () =>
      api.patch(`/automations/${automation.id}`, { status: newStatus }),
    loadingMessage: `${isActive ? "Disabling" : "Activating"} automation...`,
    successMessage: `Automation ${isActive ? "disabled" : "activated"}.`,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations"] });
      onDone();
    },
  });

  return (
    <button
      onClick={() => toggle.mutate()}
      disabled={toggle.isPending}
      className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-[var(--color-surface-2)] text-left disabled:opacity-50"
    >
      {isActive ? (
        <PowerOff className="w-3.5 h-3.5" />
      ) : (
        <Power className="w-3.5 h-3.5" />
      )}
      {isActive ? "Disable" : "Activate"}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Edit configuration modal
// ---------------------------------------------------------------------------

interface AutomationDetail extends AutomationItem {
  graph_file?: string;
  script_hash?: string;
  parameters: Array<{ name: string; type: string; default?: string }>;
  timeout_seconds: number;
}

function EditConfigurationModal({
  automation,
  onClose,
}: {
  automation: AutomationItem;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();

  // Fetch full detail to get timeout_seconds
  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["automation", automation.id],
    queryFn: () => api.get<AutomationDetail>(`/automations/${automation.id}`),
  });

  const [form, setForm] = useState({
    name: automation.name,
    description: automation.description || "",
    status: automation.status as string,
    timeout_seconds: 300,
    tags: automation.tags,
  });

  // Update timeout once detail loads
  const [timeoutLoaded, setTimeoutLoaded] = useState(false);
  useEffect(() => {
    if (detail && !timeoutLoaded) {
      setForm((prev) => ({ ...prev, timeout_seconds: detail.timeout_seconds }));
      setTimeoutLoaded(true);
    }
  }, [detail, timeoutLoaded]);

  const saveMutation = useToastMutation({
    mutationFn: () => {
      return api.patch(`/automations/${automation.id}`, {
        name: form.name,
        description: form.description || null,
        status: form.status,
        timeout_seconds: form.timeout_seconds,
        tags: form.tags,
      });
    },
    loadingMessage: "Saving configuration...",
    successMessage: "Configuration saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["automations"] });
      queryClient.invalidateQueries({ queryKey: ["automation", automation.id] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl w-[480px] max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Edit Configuration</h2>
          <button onClick={onClose} className="p-1 hover:bg-[var(--color-surface-2)] rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        {detailLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-5 h-5 animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1">Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Description</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm"
                rows={3}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Status</label>
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm"
              >
                {allStatuses.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Timeout (seconds)</label>
              <input
                type="number"
                min={10}
                max={3600}
                value={form.timeout_seconds}
                onChange={(e) =>
                  setForm({ ...form, timeout_seconds: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Tags</label>
              <TagInput
                value={form.tags}
                onChange={(tags) => setForm({ ...form, tags })}
                placeholder="tag1, tag2, tag3"
              />
            </div>

            {saveMutation.isError && (
              <p className="text-xs text-red-500">
                Failed to save. Please try again.
              </p>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[var(--color-border)]">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!form.name || saveMutation.isPending || detailLoading}
            className="px-3 py-1.5 text-xs rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50"
          >
            {saveMutation.isPending && (
              <Loader2 className="w-3 h-3 animate-spin inline mr-1" />
            )}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
