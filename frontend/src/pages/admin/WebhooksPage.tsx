import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { TagInput } from "@/components/ui/TagInput";
import {
  Plus,
  Trash2,
  Edit2,
  MoreHorizontal,
  Copy,
  RefreshCw,
  FileText,
  ChevronDown,
  ChevronRight,
  X,
  AlertTriangle,
} from "lucide-react";
import type {
  Webhook,
  WebhookListItem,
  WebhookLog,
  WebhookLogStatus,
  WebhookSourceListItem,
  IncidentSeverity,
  PaginatedResponse,
} from "@/types/api";

const SOURCE_TYPE_OPTIONS = [
  { value: "custom", label: "Custom" },
  { value: "splunk", label: "Splunk" },
  { value: "sentinel", label: "Microsoft Sentinel" },
  { value: "elastic", label: "Elastic" },
  { value: "crowdstrike", label: "CrowdStrike" },
  { value: "palo_alto", label: "Palo Alto" },
];

const SEVERITY_OPTIONS: { value: IncidentSeverity; label: string }[] = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: "informational", label: "Informational" },
];

const LOG_STATUS_STYLES: Record<WebhookLogStatus, string> = {
  success: "bg-green-500/20 text-green-400",
  error: "bg-red-500/20 text-red-400",
  rate_limited: "bg-yellow-500/20 text-yellow-400",
  normalization_failed: "bg-orange-500/20 text-orange-400",
};

export function WebhooksPage() {
  const queryClient = useQueryClient();

  // UI state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookListItem | null>(null);
  const [tokenModal, setTokenModal] = useState<{ url: string } | null>(null);
  const [logsWebhook, setLogsWebhook] = useState<WebhookListItem | null>(null);
  const [openActionMenu, setOpenActionMenu] = useState<string | null>(null);
  const [menuPos, setMenuPos] = useState<{ top: number; left: number } | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formSourceType, setFormSourceType] = useState("custom");
  const [formCustomSourceType, setFormCustomSourceType] = useState("");
  const [formSeverity, setFormSeverity] = useState<IncidentSeverity>("medium");
  const [formTags, setFormTags] = useState<string[]>([]);
  const [formRateLimit, setFormRateLimit] = useState(60);
  const [formSourceId, setFormSourceId] = useState<string>("");

  const { data: webhooksResponse, isLoading } = useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api.get<PaginatedResponse<WebhookListItem>>("/webhooks?per_page=100"),
  });

  const webhooks = webhooksResponse?.data ?? [];

  const { data: sourcesData } = useQuery({
    queryKey: ["webhook-sources"],
    queryFn: () => api.get<WebhookSourceListItem[]>("/webhook-sources"),
  });
  const sources = sourcesData ?? [];

  const createWebhook = useMutation({
    mutationFn: () => {
      const sourceType =
        formSourceType === "__custom" ? formCustomSourceType : formSourceType;
      return api.post<Webhook>("/webhooks", {
        name: formName,
        description: formDescription || null,
        source_type: sourceType,
        source_id: formSourceId || null,
        default_severity: formSeverity,
        default_tags: formTags,
        rate_limit_per_minute: formRateLimit,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      resetForm();
      setShowCreateModal(false);
      const ingestUrl = `${window.location.origin}/api/v1/webhooks/ingest/${data.secret_token}`;
      setTokenModal({ url: ingestUrl });
    },
  });

  const updateWebhook = useMutation({
    mutationFn: () => {
      if (!editingWebhook) return Promise.reject("No webhook");
      const sourceType =
        formSourceType === "__custom" ? formCustomSourceType : formSourceType;
      return api.patch<Webhook>(`/webhooks/${editingWebhook.id}`, {
        name: formName,
        description: formDescription || null,
        source_type: sourceType,
        source_id: formSourceId || null,
        default_severity: formSeverity,
        default_tags: formTags,
        rate_limit_per_minute: formRateLimit,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      resetForm();
      setEditingWebhook(null);
    },
  });

  const deleteWebhook = useMutation({
    mutationFn: (id: string) => api.delete(`/webhooks/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  const toggleWebhook = useMutation({
    mutationFn: ({ id, is_enabled }: { id: string; is_enabled: boolean }) =>
      api.patch(`/webhooks/${id}`, { is_enabled: !is_enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  const regenerateToken = useMutation({
    mutationFn: (id: string) =>
      api.post<{ secret_token: string }>(`/webhooks/${id}/regenerate-token`),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      const ingestUrl = `${window.location.origin}/api/v1/webhooks/ingest/${data.secret_token}`;
      setTokenModal({ url: ingestUrl });
    },
  });

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormSourceType("custom");
    setFormCustomSourceType("");
    setFormSeverity("medium");
    setFormTags([]);
    setFormRateLimit(60);
    setFormSourceId("");
  };

  const openEdit = (wh: WebhookListItem) => {
    // Fetch full webhook details to populate the form
    api.get<Webhook>(`/webhooks/${wh.id}`).then((full) => {
      setEditingWebhook(wh);
      setFormName(full.name);
      setFormDescription(full.description || "");
      const isKnownSource = SOURCE_TYPE_OPTIONS.some(
        (o) => o.value === full.source_type
      );
      if (isKnownSource) {
        setFormSourceType(full.source_type);
        setFormCustomSourceType("");
      } else {
        setFormSourceType("__custom");
        setFormCustomSourceType(full.source_type);
      }
      setFormSeverity(full.default_severity);
      setFormTags(full.default_tags);
      setFormRateLimit(full.rate_limit_per_minute);
      setFormSourceId(full.source_id || "");
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Webhooks</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            Manage ingest webhooks for receiving alerts from external sources.
          </p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Create Webhook
        </button>
      </div>

      {isLoading ? (
        <p className="text-[hsl(var(--muted-foreground))]">Loading...</p>
      ) : webhooks.length === 0 ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <p>No webhooks created yet.</p>
          <p className="text-sm mt-1">Create one to start ingesting alerts.</p>
        </div>
      ) : (
        <div className="border border-[hsl(var(--border))] rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="bg-[hsl(var(--accent))]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Source Type</th>
                <th className="text-center px-4 py-2 font-medium">Status</th>
                <th className="text-left px-4 py-2 font-medium">Last Received</th>
                <th className="text-right px-4 py-2 font-medium">Total Received</th>
                <th className="text-right px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {webhooks.map((wh) => (
                <tr key={wh.id} className="hover:bg-[hsl(var(--accent))]/50">
                  <td className="px-4 py-2 font-medium">{wh.name}</td>
                  <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">
                    {wh.source_type}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <button
                      onClick={() =>
                        toggleWebhook.mutate({
                          id: wh.id,
                          is_enabled: wh.is_enabled,
                        })
                      }
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium transition-colors ${
                        wh.is_enabled
                          ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                          : "bg-[hsl(var(--muted))]/50 text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))]/70"
                      }`}
                      title={wh.is_enabled ? "Click to disable" : "Click to enable"}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          wh.is_enabled ? "bg-green-400" : "bg-[hsl(var(--muted-foreground))]"
                        }`}
                      />
                      {wh.is_enabled ? "Enabled" : "Disabled"}
                    </button>
                  </td>
                  <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">
                    {wh.last_received_at ? formatDate(wh.last_received_at) : "Never"}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {wh.total_received.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="inline-block">
                      <button
                        onClick={(e) => {
                          if (openActionMenu === wh.id) {
                            setOpenActionMenu(null);
                            setMenuPos(null);
                          } else {
                            const rect = e.currentTarget.getBoundingClientRect();
                            setMenuPos({ top: rect.bottom + 4, left: rect.right });
                            setOpenActionMenu(wh.id);
                          }
                        }}
                        className="p-1 rounded hover:bg-[hsl(var(--accent))] transition-colors"
                        title="Actions"
                      >
                        <MoreHorizontal className="w-4 h-4" />
                      </button>
                      {openActionMenu === wh.id && menuPos && (
                        <>
                          <div
                            className="fixed inset-0 z-40"
                            onClick={() => { setOpenActionMenu(null); setMenuPos(null); }}
                          />
                          <div className="fixed z-50 w-52 bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl py-1" style={{ top: menuPos.top, left: menuPos.left - 208 }}>
                            <button
                              onClick={() => {
                                setOpenActionMenu(null);
                                openEdit(wh);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-[hsl(var(--accent))] text-left"
                            >
                              <Edit2 className="w-3.5 h-3.5" /> Edit
                            </button>
                            <button
                              onClick={() => {
                                setOpenActionMenu(null);
                                setLogsWebhook(wh);
                              }}
                              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-[hsl(var(--accent))] text-left"
                            >
                              <FileText className="w-3.5 h-3.5" /> View Logs
                            </button>
                            <div className="border-t border-[hsl(var(--border))] my-1" />
                            <button
                              onClick={() => {
                                setOpenActionMenu(null);
                                if (
                                  confirm(
                                    "Are you sure? The old URL will stop working."
                                  )
                                ) {
                                  regenerateToken.mutate(wh.id);
                                }
                              }}
                              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-[hsl(var(--accent))] text-left text-yellow-400"
                            >
                              <RefreshCw className="w-3.5 h-3.5" /> Regenerate Token
                            </button>
                            <button
                              onClick={() => {
                                setOpenActionMenu(null);
                                if (confirm(`Delete webhook "${wh.name}"?`)) {
                                  deleteWebhook.mutate(wh.id);
                                }
                              }}
                              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-red-500/20 text-red-400 text-left"
                            >
                              <Trash2 className="w-3.5 h-3.5" /> Delete
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {(showCreateModal || editingWebhook) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[500px] max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
              <h3 className="font-semibold text-sm">
                {editingWebhook ? "Edit Webhook" : "Create Webhook"}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingWebhook(null);
                  resetForm();
                }}
                className="p-1 rounded hover:bg-[hsl(var(--accent))]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              {/* Name */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Name
                </label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Splunk Production Alerts"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>

              {/* Description */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Description
                </label>
                <textarea
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  rows={2}
                  placeholder="What this webhook receives"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>

              {/* Source Type */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Source Type
                </label>
                <select
                  value={formSourceType}
                  onChange={(e) => setFormSourceType(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                >
                  {SOURCE_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                  <option value="__custom">Other (custom)...</option>
                </select>
                {formSourceType === "__custom" && (
                  <input
                    type="text"
                    value={formCustomSourceType}
                    onChange={(e) => setFormCustomSourceType(e.target.value)}
                    placeholder="Enter custom source type"
                    className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] mt-2"
                  />
                )}
              </div>

              {/* Webhook Source */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Source (determines automations)
                </label>
                <select
                  value={formSourceId}
                  onChange={(e) => setFormSourceId(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                >
                  <option value="">No source</option>
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.automation_count} automations)
                    </option>
                  ))}
                </select>
                <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                  When a source is assigned, its linked automations will run on ingested incidents.
                </p>
              </div>

              {/* Default Severity */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Default Severity
                </label>
                <select
                  value={formSeverity}
                  onChange={(e) => setFormSeverity(e.target.value as IncidentSeverity)}
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                >
                  {SEVERITY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Default Tags */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Default Tags
                </label>
                <TagInput
                  value={formTags}
                  onChange={setFormTags}
                  placeholder="Add a tag..."
                />
              </div>

              {/* Rate Limit */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                  Rate Limit (per minute)
                </label>
                <input
                  type="number"
                  value={formRateLimit}
                  onChange={(e) => setFormRateLimit(Number(e.target.value))}
                  min={1}
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[hsl(var(--border))]">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setEditingWebhook(null);
                  resetForm();
                }}
                className="px-3 py-1.5 text-sm rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  editingWebhook ? updateWebhook.mutate() : createWebhook.mutate()
                }
                disabled={
                  !formName.trim() ||
                  (formSourceType === "__custom" && !formCustomSourceType.trim()) ||
                  createWebhook.isPending ||
                  updateWebhook.isPending
                }
                className="px-3 py-1.5 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
              >
                {editingWebhook ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Token Display Modal */}
      {tokenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[520px]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
              <h3 className="font-semibold text-sm">Webhook Ingest URL</h3>
              <button
                onClick={() => setTokenModal(null)}
                className="p-1 rounded hover:bg-[hsl(var(--accent))]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3">
              <div className="flex items-center gap-2 p-3 rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]">
                <code className="flex-1 text-xs break-all font-mono">
                  {tokenModal.url}
                </code>
                <button
                  onClick={() => navigator.clipboard.writeText(tokenModal.url)}
                  className="p-1.5 rounded hover:bg-[hsl(var(--accent))] shrink-0"
                  title="Copy to clipboard"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
              <div className="flex items-start gap-2 p-3 rounded bg-yellow-500/10 border border-yellow-500/20">
                <AlertTriangle className="w-4 h-4 text-yellow-400 shrink-0 mt-0.5" />
                <p className="text-xs text-yellow-400">
                  Save this URL — the token won't be shown again in full.
                </p>
              </div>
            </div>
            <div className="flex justify-end px-4 py-3 border-t border-[hsl(var(--border))]">
              <button
                onClick={() => setTokenModal(null)}
                className="px-3 py-1.5 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {logsWebhook && (
        <WebhookLogsModal
          webhook={logsWebhook}
          onClose={() => setLogsWebhook(null)}
        />
      )}
    </div>
  );
}

function WebhookLogsModal({
  webhook,
  onClose,
}: {
  webhook: WebhookListItem;
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const perPage = 25;

  const { data: logsResponse, isLoading } = useQuery({
    queryKey: ["webhook-logs", webhook.id, page, statusFilter],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
      });
      if (statusFilter) params.set("status", statusFilter);
      return api.get<PaginatedResponse<WebhookLog>>(
        `/webhooks/${webhook.id}/logs?${params.toString()}`
      );
    },
  });

  const logs = logsResponse?.data ?? [];
  const meta = logsResponse?.meta;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[900px] max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
          <h3 className="font-semibold text-sm">
            Webhook Logs — {webhook.name}
          </h3>
          <div className="flex items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="px-2 py-1 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
            >
              <option value="">All statuses</option>
              <option value="success">Success</option>
              <option value="error">Error</option>
              <option value="rate_limited">Rate Limited</option>
              <option value="normalization_failed">Normalization Failed</option>
            </select>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-[hsl(var(--accent))]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-[hsl(var(--muted-foreground))]">
              Loading...
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
              <p>No logs found.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[hsl(var(--accent))] sticky top-0">
                <tr>
                  <th className="w-8 px-2 py-2" />
                  <th className="text-left px-4 py-2 font-medium">Status</th>
                  <th className="text-left px-4 py-2 font-medium">Remote IP</th>
                  <th className="text-right px-4 py-2 font-medium">
                    Processing Time
                  </th>
                  <th className="text-left px-4 py-2 font-medium">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[hsl(var(--border))]">
                {logs.map((log) => (
                  <LogRow
                    key={log.id}
                    log={log}
                    expanded={expandedLog === log.id}
                    onToggle={() =>
                      setExpandedLog(expandedLog === log.id ? null : log.id)
                    }
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {meta && meta.total_pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[hsl(var(--border))]">
            <p className="text-xs text-[hsl(var(--muted-foreground))]">
              Showing {(page - 1) * perPage + 1}–
              {Math.min(page * perPage, meta.total)} of {meta.total}
            </p>
            <div className="flex gap-1">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className="px-2 py-1 text-xs rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))] disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= meta.total_pages}
                className="px-2 py-1 text-xs rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))] disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function LogRow({
  log,
  expanded,
  onToggle,
}: {
  log: WebhookLog;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="hover:bg-[hsl(var(--accent))]/50 cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-2 py-2 text-center">
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5 inline" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 inline" />
          )}
        </td>
        <td className="px-4 py-2">
          <span
            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
              LOG_STATUS_STYLES[log.status]
            }`}
          >
            {log.status.replace(/_/g, " ")}
          </span>
        </td>
        <td className="px-4 py-2 text-[hsl(var(--muted-foreground))] font-mono text-xs">
          {log.remote_ip || "-"}
        </td>
        <td className="px-4 py-2 text-right tabular-nums text-[hsl(var(--muted-foreground))]">
          {log.processing_time_ms != null ? `${log.processing_time_ms}ms` : "-"}
        </td>
        <td className="px-4 py-2 text-[hsl(var(--muted-foreground))]">
          {formatDate(log.created_at)}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="px-4 py-3 bg-[hsl(var(--accent))]/30">
            <div className="space-y-3">
              {log.error_message && (
                <div>
                  <p className="text-xs font-medium text-red-400 mb-1">
                    Error Message
                  </p>
                  <p className="text-xs text-red-300">{log.error_message}</p>
                </div>
              )}
              <div>
                <p className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1">
                  Request Body
                </p>
                <pre className="text-xs font-mono p-2 rounded bg-[hsl(var(--background))] border border-[hsl(var(--border))] overflow-x-auto max-h-[300px] overflow-y-auto">
                  {JSON.stringify(log.request_body, null, 2)}
                </pre>
              </div>
              {log.normalized_data && (
                <div>
                  <p className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1">
                    Normalized Data
                  </p>
                  <pre className="text-xs font-mono p-2 rounded bg-[hsl(var(--background))] border border-[hsl(var(--border))] overflow-x-auto max-h-[300px] overflow-y-auto">
                    {JSON.stringify(log.normalized_data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
