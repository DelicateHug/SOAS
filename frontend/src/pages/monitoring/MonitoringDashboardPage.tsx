import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { formatDate } from "@/lib/utils";
import {
  Activity,
  Bell,
  CheckCircle2,
  Clock,
  Database,
  GitBranch,
  HardDrive,
  Heart,
  RefreshCw,
  Server,
  Users,
  Wifi,
  XCircle,
  Plus,
  Power,
  Trash2,
} from "lucide-react";
import { MetricsChart } from "./MetricsChart";
import type {
  SystemHealthOverview,
  AlertItem,
  AlertRule,
  QuorumStatus,
  MonitoringAgent,
  ComponentHealth,
  PaginatedResponse,
  GitSyncStatus,
  GitSyncLogsResponse,
} from "@/types/api";

const STATUS_COLORS: Record<string, string> = {
  healthy: "text-green-500",
  degraded: "text-yellow-500",
  unhealthy: "text-red-500",
  unknown: "text-gray-400",
};

const STATUS_BG: Record<string, string> = {
  healthy: "bg-green-500/10 border-green-500/20",
  degraded: "bg-yellow-500/10 border-yellow-500/20",
  unhealthy: "bg-red-500/10 border-red-500/20",
  unknown: "bg-gray-500/10 border-gray-500/20",
};

const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  warning: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  critical: "bg-red-500/10 text-red-500 border-red-500/20",
};

const COMPONENT_ICONS: Record<string, typeof Server> = {
  api: Server,
  postgres: Database,
  redis: HardDrive,
  celery_worker: RefreshCw,
  celery_beat: Activity,
  websocket: Wifi,
};

const COMPONENT_LABELS: Record<string, string> = {
  api: "API Server",
  postgres: "PostgreSQL",
  redis: "Redis",
  celery_worker: "Celery Workers",
  celery_beat: "Celery Beat",
  websocket: "WebSockets",
};

type Tab = "overview" | "alerts" | "rules" | "quorum" | "agents" | "git_sync";

export function MonitoringDashboardPage() {
  const { hasPermission } = useAuthStore();
  const isAdmin = hasPermission("monitoring:admin");
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const tabs: { id: Tab; label: string; adminOnly?: boolean }[] = [
    { id: "overview", label: "Overview" },
    { id: "alerts", label: "Alerts" },
    { id: "rules", label: "Alert Rules", adminOnly: true },
    { id: "quorum", label: "Quorum" },
    { id: "agents", label: "Agents" },
    { id: "git_sync", label: "Git Sync" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">System Monitoring</h1>

      {/* Tab navigation */}
      <div className="flex gap-1 mb-6 border-b border-[hsl(var(--border))]">
        {tabs.map(
          (tab) =>
            (!tab.adminOnly || isAdmin) && (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
                    : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                }`}
              >
                {tab.label}
              </button>
            )
        )}
      </div>

      {activeTab === "overview" && <OverviewPanel />}
      {activeTab === "alerts" && <AlertsPanel isAdmin={isAdmin} />}
      {activeTab === "rules" && isAdmin && <AlertRulesPanel />}
      {activeTab === "quorum" && <QuorumPanel />}
      {activeTab === "agents" && <AgentsPanel isAdmin={isAdmin} />}
      {activeTab === "git_sync" && <GitSyncPanel isAdmin={isAdmin} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview Panel
// ---------------------------------------------------------------------------

const TIMEFRAME_OPTIONS = [
  { value: 5, label: "5m" },
  { value: 10, label: "10m" },
  { value: 30, label: "30m" },
  { value: 60, label: "1h" },
  { value: 360, label: "6h" },
  { value: 1440, label: "24h" },
] as const;

function OverviewPanel() {
  const [timeframeMinutes, setTimeframeMinutes] = useState(10);

  const { data: overview, isLoading } = useQuery({
    queryKey: ["monitoring-overview", timeframeMinutes],
    queryFn: () =>
      api.get<{
        health: SystemHealthOverview;
        alert_summary: Record<string, number>;
        quorum: QuorumStatus;
      }>(`/monitoring/overview?minutes=${timeframeMinutes}`),
    refetchInterval: 15000,
  });

  const health = overview?.health;
  const alertSummary = overview?.alert_summary;
  const quorum = overview?.quorum;

  if (isLoading) {
    return <p className="text-[hsl(var(--muted-foreground))]">Loading health data...</p>;
  }

  const overallStatus = health?.overall_status ?? "unknown";
  const uptimeHours = health ? Math.floor(health.uptime_seconds / 3600) : 0;
  const uptimeMinutes = health ? Math.floor((health.uptime_seconds % 3600) / 60) : 0;
  const totalAlerts = alertSummary
    ? Object.values(alertSummary).reduce((a, b) => a + b, 0)
    : 0;

  // Group components by type (skip duplicates, keep aggregate for workers)
  const componentsByType = new Map<string, ComponentHealth>();
  for (const c of health?.components ?? []) {
    if (c.component_id === "aggregate" || !componentsByType.has(c.component_type)) {
      componentsByType.set(c.component_type, c);
    }
  }

  const chartHours = Math.max(timeframeMinutes / 60, 1);
  const timeframeLabel = TIMEFRAME_OPTIONS.find(
    (o) => o.value === timeframeMinutes
  )?.label ?? `${timeframeMinutes}m`;

  return (
    <div className="space-y-6">
      {/* Timeframe selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-[hsl(var(--muted-foreground))]">
          Timeframe:
        </span>
        <div className="flex gap-1">
          {TIMEFRAME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTimeframeMinutes(opt.value)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                timeframeMinutes === opt.value
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                  : "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          label="System Status"
          value={overallStatus.charAt(0).toUpperCase() + overallStatus.slice(1)}
          icon={Heart}
          colorClass={STATUS_COLORS[overallStatus] ?? "text-gray-400"}
        />
        <StatCard
          label="Uptime"
          value={`${uptimeHours}h ${uptimeMinutes}m`}
          icon={Activity}
          colorClass="text-[hsl(var(--primary))]"
        />
        <StatCard
          label="Active Alerts"
          value={String(totalAlerts)}
          icon={Bell}
          colorClass={totalAlerts > 0 ? "text-red-500" : "text-green-500"}
        />
        <StatCard
          label="Quorum"
          value={
            quorum
              ? quorum.has_quorum
                ? `${quorum.active_members}/${quorum.total_members}`
                : "LOST"
              : "N/A"
          }
          icon={Users}
          colorClass={
            quorum?.has_quorum ? "text-green-500" : "text-red-500"
          }
        />
      </div>

      {/* Component health cards */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Component Health</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from(componentsByType.entries()).map(([type, comp]) => {
            const Icon = COMPONENT_ICONS[type] ?? Server;
            return (
              <div
                key={type}
                className={`border rounded-lg p-4 ${STATUS_BG[comp.status]}`}
              >
                <div className="flex items-center gap-3 mb-3">
                  <Icon className={`w-5 h-5 ${STATUS_COLORS[comp.status]}`} />
                  <div>
                    <h3 className="font-semibold text-sm">
                      {COMPONENT_LABELS[type] ?? type}
                    </h3>
                    <p
                      className={`text-xs font-medium ${STATUS_COLORS[comp.status]}`}
                    >
                      {comp.status.toUpperCase()}
                    </p>
                  </div>
                </div>
                <div className="space-y-1">
                  {Object.entries(comp.metrics).map(([key, val]) => (
                    <div
                      key={key}
                      className="flex justify-between text-xs text-[hsl(var(--muted-foreground))]"
                    >
                      <span>{key.replace(/_/g, " ")}</span>
                      <span className="font-mono">
                        {typeof val === "number" ? val.toLocaleString() : val}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Metrics Charts */}
      <div>
        <h2 className="text-lg font-semibold mb-3">
          Metrics ({timeframeLabel})
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <MetricsChart
            componentType="api"
            componentId="backend"
            metricKey="response_time_ms"
            label="API Response Time (ms)"
            hours={chartHours}
            color="#3b82f6"
          />
          <MetricsChart
            componentType="postgres"
            componentId="primary"
            metricKey="query_latency_ms"
            label="Database Latency (ms)"
            hours={chartHours}
            color="#8b5cf6"
          />
          <MetricsChart
            componentType="redis"
            componentId="primary"
            metricKey="memory_mb"
            label="Redis Memory (MB)"
            hours={chartHours}
            color="#f59e0b"
          />
          <MetricsChart
            componentType="celery_worker"
            componentId="aggregate"
            metricKey="total_queue_depth"
            label="Task Queue Depth"
            hours={chartHours}
            color="#ef4444"
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alerts Panel
// ---------------------------------------------------------------------------

function AlertsPanel({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("active");

  const { data: alertsResp, isLoading } = useQuery({
    queryKey: ["monitoring-alerts", statusFilter],
    queryFn: () =>
      api.get<PaginatedResponse<AlertItem>>(
        `/monitoring/alerts?status=${statusFilter}`
      ),
    refetchInterval: 15000,
  });

  const acknowledgeMut = useMutation({
    mutationFn: (id: string) =>
      api.post(`/monitoring/alerts/${id}/acknowledge`, {}),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["monitoring-alerts"] }),
  });

  const resolveMut = useMutation({
    mutationFn: (id: string) =>
      api.post(`/monitoring/alerts/${id}/resolve`, {}),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["monitoring-alerts"] }),
  });

  const alerts = alertsResp?.data ?? [];

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex gap-2">
        {["active", "acknowledged", "resolved"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 text-sm rounded-md border ${
              statusFilter === s
                ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] border-[hsl(var(--primary))]"
                : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]"
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-[hsl(var(--muted-foreground))]">Loading alerts...</p>
      ) : alerts.length === 0 ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No {statusFilter} alerts</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className="border border-[hsl(var(--border))] rounded-lg p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border ${
                        SEVERITY_COLORS[alert.severity]
                      }`}
                    >
                      {alert.severity}
                    </span>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">
                      {alert.component_type}/{alert.component_id}
                    </span>
                  </div>
                  <p className="font-medium text-sm truncate">{alert.title}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {alert.message}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {formatDate(alert.created_at)}
                  </p>
                </div>
                {isAdmin && alert.status === "active" && (
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => acknowledgeMut.mutate(alert.id)}
                      className="px-3 py-1 text-xs rounded-md bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 hover:bg-yellow-500/20"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={() => resolveMut.mutate(alert.id)}
                      className="px-3 py-1 text-xs rounded-md bg-green-500/10 text-green-500 border border-green-500/20 hover:bg-green-500/20"
                    >
                      Resolve
                    </button>
                  </div>
                )}
                {isAdmin && alert.status === "acknowledged" && (
                  <button
                    onClick={() => resolveMut.mutate(alert.id)}
                    className="px-3 py-1 text-xs rounded-md bg-green-500/10 text-green-500 border border-green-500/20 hover:bg-green-500/20 shrink-0"
                  >
                    Resolve
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alert Rules Panel (admin only)
// ---------------------------------------------------------------------------

function AlertRulesPanel() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: rules, isLoading } = useQuery({
    queryKey: ["monitoring-alert-rules"],
    queryFn: () => api.get<AlertRule[]>("/monitoring/alert-rules"),
  });

  const toggleMut = useMutation({
    mutationFn: (rule: AlertRule) =>
      api.patch(`/monitoring/alert-rules/${rule.id}`, {
        is_enabled: !rule.is_enabled,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["monitoring-alert-rules"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.delete(`/monitoring/alert-rules/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["monitoring-alert-rules"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Alert Rules</h2>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90"
        >
          <Plus className="w-4 h-4" />
          Create Rule
        </button>
      </div>

      {isLoading ? (
        <p className="text-[hsl(var(--muted-foreground))]">Loading rules...</p>
      ) : (
        <div className="space-y-2">
          {(rules ?? []).map((rule) => (
            <div
              key={rule.id}
              className="border border-[hsl(var(--border))] rounded-lg p-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        rule.is_enabled ? "bg-green-500" : "bg-gray-400"
                      }`}
                    />
                    <span className="font-medium text-sm">{rule.name}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border ${
                        SEVERITY_COLORS[rule.severity]
                      }`}
                    >
                      {rule.severity}
                    </span>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    {rule.component_type} / {rule.metric_key}{" "}
                    {rule.condition} {rule.threshold} (cooldown:{" "}
                    {rule.cooldown_seconds}s)
                  </p>
                  {rule.description && (
                    <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                      {rule.description}
                    </p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => toggleMut.mutate(rule)}
                    className="p-2 rounded-md hover:bg-[hsl(var(--accent))]"
                    title={rule.is_enabled ? "Disable" : "Enable"}
                  >
                    <Power
                      className={`w-4 h-4 ${
                        rule.is_enabled ? "text-green-500" : "text-gray-400"
                      }`}
                    />
                  </button>
                  <button
                    onClick={() => deleteMut.mutate(rule.id)}
                    className="p-2 rounded-md hover:bg-[hsl(var(--accent))]"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateRuleModal onClose={() => setShowCreate(false)} />
      )}
    </div>
  );
}

function CreateRuleModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    description: "",
    component_type: "api",
    metric_key: "",
    condition: "gt",
    threshold: 0,
    severity: "warning",
    cooldown_seconds: 300,
  });

  const createMut = useMutation({
    mutationFn: (data: typeof form) =>
      api.post("/monitoring/alert-rules", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring-alert-rules"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[hsl(var(--background))] border border-[hsl(var(--border))] rounded-lg p-6 w-full max-w-lg">
        <h3 className="text-lg font-semibold mb-4">Create Alert Rule</h3>
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Description</label>
            <input
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
              className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Component</label>
              <select
                value={form.component_type}
                onChange={(e) =>
                  setForm({ ...form, component_type: e.target.value })
                }
                className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
              >
                <option value="api">API</option>
                <option value="postgres">PostgreSQL</option>
                <option value="redis">Redis</option>
                <option value="celery_worker">Celery Worker</option>
                <option value="celery_beat">Celery Beat</option>
                <option value="websocket">WebSocket</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Metric Key</label>
              <input
                value={form.metric_key}
                onChange={(e) =>
                  setForm({ ...form, metric_key: e.target.value })
                }
                placeholder="e.g. response_time_ms"
                className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-sm font-medium">Condition</label>
              <select
                value={form.condition}
                onChange={(e) =>
                  setForm({ ...form, condition: e.target.value })
                }
                className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
              >
                <option value="gt">&gt; (greater than)</option>
                <option value="gte">&gt;= (greater or equal)</option>
                <option value="lt">&lt; (less than)</option>
                <option value="lte">&lt;= (less or equal)</option>
                <option value="eq">= (equal)</option>
                <option value="ne">!= (not equal)</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Threshold</label>
              <input
                type="number"
                value={form.threshold}
                onChange={(e) =>
                  setForm({ ...form, threshold: Number(e.target.value) })
                }
                className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Severity</label>
              <select
                value={form.severity}
                onChange={(e) =>
                  setForm({ ...form, severity: e.target.value })
                }
                className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
              >
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">
              Cooldown (seconds)
            </label>
            <input
              type="number"
              value={form.cooldown_seconds}
              onChange={(e) =>
                setForm({
                  ...form,
                  cooldown_seconds: Number(e.target.value),
                })
              }
              className="w-full mt-1 px-3 py-2 border border-[hsl(var(--border))] rounded-md text-sm bg-transparent"
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]"
          >
            Cancel
          </button>
          <button
            onClick={() => createMut.mutate(form)}
            disabled={!form.name || !form.metric_key}
            className="px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Quorum Panel
// ---------------------------------------------------------------------------

function QuorumPanel() {
  const { data: quorum, isLoading } = useQuery({
    queryKey: ["monitoring-quorum"],
    queryFn: () => api.get<QuorumStatus>("/monitoring/quorum"),
    refetchInterval: 15000,
  });

  if (isLoading) {
    return <p className="text-[hsl(var(--muted-foreground))]">Loading quorum status...</p>;
  }

  if (!quorum) {
    return <p className="text-[hsl(var(--muted-foreground))]">No quorum data available</p>;
  }

  return (
    <div className="space-y-6">
      {/* Quorum status card */}
      <div
        className={`border rounded-lg p-6 ${
          quorum.has_quorum
            ? "bg-green-500/10 border-green-500/20"
            : "bg-red-500/10 border-red-500/20"
        }`}
      >
        <div className="flex items-center gap-4">
          {quorum.has_quorum ? (
            <CheckCircle2 className="w-10 h-10 text-green-500" />
          ) : (
            <XCircle className="w-10 h-10 text-red-500" />
          )}
          <div>
            <h2 className="text-xl font-bold">
              {quorum.has_quorum ? "Quorum Established" : "QUORUM LOST"}
            </h2>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              {quorum.active_members} of {quorum.total_members} members active
              (threshold: {quorum.quorum_threshold})
            </p>
          </div>
        </div>
      </div>

      {/* Member table */}
      <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[hsl(var(--muted))]">
              <th className="text-left px-4 py-3 font-medium">Instance ID</th>
              <th className="text-left px-4 py-3 font-medium">Hostname</th>
              <th className="text-left px-4 py-3 font-medium">Started</th>
              <th className="text-left px-4 py-3 font-medium">
                Last Heartbeat
              </th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {quorum.members.map((member) => (
              <tr
                key={member.instance_id}
                className="border-t border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
              >
                <td className="px-4 py-3 font-mono text-xs">
                  {member.instance_id.slice(0, 8)}...
                </td>
                <td className="px-4 py-3">{member.hostname}</td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                  {formatDate(member.started_at)}
                </td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                  {formatDate(member.last_heartbeat)}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-medium ${
                      member.is_alive ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        member.is_alive ? "bg-green-500" : "bg-red-500"
                      }`}
                    />
                    {member.is_alive ? "Alive" : "Dead"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Agents Panel
// ---------------------------------------------------------------------------

function AgentsPanel({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();

  const { data: agents, isLoading } = useQuery({
    queryKey: ["monitoring-agents"],
    queryFn: () => api.get<MonitoringAgent[]>("/monitoring/agents"),
    refetchInterval: 15000,
  });

  const toggleMut = useMutation({
    mutationFn: (agent: MonitoringAgent) =>
      api.patch(`/monitoring/agents/${agent.id}`, {
        is_enabled: !agent.is_enabled,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["monitoring-agents"] }),
  });

  if (isLoading) {
    return <p className="text-[hsl(var(--muted-foreground))]">Loading agents...</p>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Monitoring Agents</h2>
      <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[hsl(var(--muted))]">
              <th className="text-left px-4 py-3 font-medium">Agent</th>
              <th className="text-left px-4 py-3 font-medium">Monitors</th>
              <th className="text-left px-4 py-3 font-medium">Interval</th>
              <th className="text-left px-4 py-3 font-medium">Last Check</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
              <th className="text-left px-4 py-3 font-medium">Failures</th>
              {isAdmin && (
                <th className="text-left px-4 py-3 font-medium">Actions</th>
              )}
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent) => (
              <tr
                key={agent.id}
                className="border-t border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
              >
                <td className="px-4 py-3">
                  <div>
                    <span className="font-medium">{agent.name}</span>
                    {agent.description && (
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">
                        {agent.description}
                      </p>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  {COMPONENT_LABELS[agent.component_type] ??
                    agent.component_type}
                </td>
                <td className="px-4 py-3">{agent.check_interval_seconds}s</td>
                <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                  {agent.last_check_at
                    ? formatDate(agent.last_check_at)
                    : "Never"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-medium ${
                      !agent.is_enabled
                        ? "text-gray-400"
                        : agent.is_alive
                        ? "text-green-500"
                        : "text-red-500"
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        !agent.is_enabled
                          ? "bg-gray-400"
                          : agent.is_alive
                          ? "bg-green-500"
                          : "bg-red-500"
                      }`}
                    />
                    {!agent.is_enabled
                      ? "Disabled"
                      : agent.is_alive
                      ? "Alive"
                      : "Dead"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {agent.consecutive_failures > 0 ? (
                    <span className="text-red-500 font-medium">
                      {agent.consecutive_failures}
                    </span>
                  ) : (
                    <span className="text-[hsl(var(--muted-foreground))]">
                      0
                    </span>
                  )}
                </td>
                {isAdmin && (
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleMut.mutate(agent)}
                      className="p-2 rounded-md hover:bg-[hsl(var(--accent))]"
                      title={agent.is_enabled ? "Disable" : "Enable"}
                    >
                      <Power
                        className={`w-4 h-4 ${
                          agent.is_enabled ? "text-green-500" : "text-gray-400"
                        }`}
                      />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Git Sync Panel
// ---------------------------------------------------------------------------

function GitSyncPanel({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["git-sync-status"],
    queryFn: () => api.get<GitSyncStatus>("/git-sync/status"),
    refetchInterval: 30000,
  });

  const { data: logsResp } = useQuery({
    queryKey: ["git-sync-logs"],
    queryFn: () => api.get<GitSyncLogsResponse>("/git-sync/logs?limit=10"),
    refetchInterval: 30000,
  });

  const syncMut = useMutation({
    mutationFn: () => api.post("/git-sync/sync", {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git-sync-status"] });
      queryClient.invalidateQueries({ queryKey: ["git-sync-logs"] });
    },
  });

  if (isLoading) {
    return (
      <p className="text-[hsl(var(--muted-foreground))]">
        Loading git sync status...
      </p>
    );
  }

  const logs = logsResp?.data ?? [];

  // Compute next sync time
  const getNextSync = () => {
    if (!status?.enabled) return "Disabled";
    const interval = (status?.interval_seconds ?? 300) * 1000;
    if (!status?.last_sync_at) {
      // Never synced — show interval as max wait
      const secs = Math.round(interval / 1000);
      return `≤ ${Math.floor(secs / 60)}m ${secs % 60}s`;
    }
    const lastSync = new Date(status.last_sync_at).getTime();
    const nextSync = lastSync + interval;
    const now = Date.now();
    if (nextSync <= now) return "Due now";
    const diffSec = Math.round((nextSync - now) / 1000);
    if (diffSec < 60) return `${diffSec}s`;
    return `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`;
  };

  return (
    <div className="space-y-6">
      {/* Status cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <StatCard
          label="Git Sync"
          value={status?.enabled ? "Enabled" : "Disabled"}
          icon={GitBranch}
          colorClass={status?.enabled ? "text-green-500" : "text-gray-400"}
        />
        <StatCard
          label="Last Sync"
          value={
            status?.last_sync_at
              ? formatDate(status.last_sync_at)
              : "Never"
          }
          icon={RefreshCw}
          colorClass="text-[hsl(var(--primary))]"
        />
        <StatCard
          label="Next Sync"
          value={getNextSync()}
          icon={Clock}
          colorClass={
            status?.enabled ? "text-blue-500" : "text-gray-400"
          }
        />
        <StatCard
          label="Last Status"
          value={status?.last_status ?? "N/A"}
          icon={
            status?.last_status === "success" ? CheckCircle2 : Activity
          }
          colorClass={
            status?.last_status === "success"
              ? "text-green-500"
              : status?.last_status === "failed"
              ? "text-red-500"
              : "text-gray-400"
          }
        />
        <StatCard
          label="Repository"
          value={status?.repo_initialized ? "Initialized" : "Not Set Up"}
          icon={Database}
          colorClass={
            status?.repo_initialized ? "text-green-500" : "text-yellow-500"
          }
        />
      </div>

      {/* Repo info + Sync button */}
      <div className="border border-[hsl(var(--border))] rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Repository Details</h2>
          {isAdmin && status?.enabled && (
            <button
              onClick={() => syncMut.mutate()}
              disabled={syncMut.isPending}
              className="flex items-center gap-2 px-3 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
            >
              <RefreshCw
                className={`w-4 h-4 ${syncMut.isPending ? "animate-spin" : ""}`}
              />
              {syncMut.isPending ? "Syncing..." : "Sync Now"}
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-[hsl(var(--muted-foreground))]">
              Remote URL:{" "}
            </span>
            <span className="font-mono">
              {status?.remote_url || "Local only"}
            </span>
          </div>
          <div>
            <span className="text-[hsl(var(--muted-foreground))]">
              Branch:{" "}
            </span>
            <span className="font-mono">{status?.branch}</span>
          </div>
          <div>
            <span className="text-[hsl(var(--muted-foreground))]">
              Sync Interval:{" "}
            </span>
            <span>{status?.interval_seconds}s</span>
          </div>
          {status?.last_commit && (
            <div>
              <span className="text-[hsl(var(--muted-foreground))]">
                Last Commit:{" "}
              </span>
              <span className="font-mono text-xs">
                {status.last_commit.sha.slice(0, 8)}
              </span>
              <span className="text-[hsl(var(--muted-foreground))]">
                {" "}
                - {status.last_commit.message}
              </span>
            </div>
          )}
        </div>
        {status?.entity_types && status.entity_types.length > 0 && (
          <div className="mt-3">
            <span className="text-sm text-[hsl(var(--muted-foreground))]">
              Synced entities:{" "}
            </span>
            <div className="flex flex-wrap gap-1 mt-1">
              {status.entity_types.map((et) => (
                <span
                  key={et}
                  className="text-xs px-2 py-0.5 rounded-full bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))]"
                >
                  {et.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sync history */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Sync History</h2>
        {logs.length === 0 ? (
          <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
            <GitBranch className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No sync history yet</p>
          </div>
        ) : (
          <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[hsl(var(--muted))]">
                  <th className="text-left px-4 py-3 font-medium">Time</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Pushed</th>
                  <th className="text-left px-4 py-3 font-medium">Pulled</th>
                  <th className="text-left px-4 py-3 font-medium">
                    Duration
                  </th>
                  <th className="text-left px-4 py-3 font-medium">
                    Triggered By
                  </th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className="border-t border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                  >
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                      {formatDate(log.started_at)}
                    </td>
                    <td className="px-4 py-3">{log.sync_type}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 text-xs font-medium ${
                          log.status === "success"
                            ? "text-green-500"
                            : log.status === "failed"
                            ? "text-red-500"
                            : "text-yellow-500"
                        }`}
                      >
                        <span
                          className={`w-2 h-2 rounded-full ${
                            log.status === "success"
                              ? "bg-green-500"
                              : log.status === "failed"
                              ? "bg-red-500"
                              : "bg-yellow-500"
                          }`}
                        />
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">{log.entities_pushed}</td>
                    <td className="px-4 py-3">{log.entities_pulled}</td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                      {log.duration_ms ? `${log.duration_ms}ms` : "-"}
                    </td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">
                      {log.triggered_by === "scheduled"
                        ? "Scheduled"
                        : "Manual"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  icon: Icon,
  colorClass,
}: {
  label: string;
  value: string;
  icon: typeof Server;
  colorClass: string;
}) {
  return (
    <div className="border border-[hsl(var(--border))] rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-[hsl(var(--muted-foreground))]">
          {label}
        </span>
        <Icon className={`w-5 h-5 ${colorClass}`} />
      </div>
      <p className={`text-2xl font-bold ${colorClass}`}>{value}</p>
    </div>
  );
}
