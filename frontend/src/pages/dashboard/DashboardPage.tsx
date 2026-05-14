import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AlertTriangle, FolderOpen, Zap, Clock, Activity, TrendingUp } from "lucide-react";
import { formatDate } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import type { TimelineEntry } from "@/types/api";

interface DashboardStats {
  incidents: {
    open: number;
    total: number;
    by_status: Record<string, number>;
    by_severity: Record<string, number>;
    daily: Array<{ date: string; count: number }>;
    mttr_hours: number | null;
  };
  cases: { open: number };
  automations: { active: number };
  executions: {
    total: number;
    running: number;
    completed: number;
    failed: number;
    avg_duration_ms: number | null;
  };
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
  informational: "#6b7280",
};

const STATUS_COLORS: Record<string, string> = {
  detected: "#ef4444",
  triaging: "#eab308",
  investigating: "#3b82f6",
  containing: "#a855f7",
  remediating: "#6366f1",
  resolved: "#22c55e",
  closed: "#6b7280",
  false_positive: "#9ca3af",
};

export function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get<DashboardStats>("/dashboard/stats"),
    refetchInterval: 30000,
  });

  const { data: activity } = useQuery({
    queryKey: ["dashboard-activity"],
    queryFn: () => api.get<TimelineEntry[]>("/dashboard/activity?limit=10"),
  });

  const severityData = stats
    ? Object.entries(stats.incidents.by_severity).map(([name, value]) => ({ name, value }))
    : [];

  const statusData = stats
    ? Object.entries(stats.incidents.by_status).map(([name, value]) => ({ name, value }))
    : [];

  const dailyData = stats?.incidents.daily.map((d) => ({
    date: new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    count: d.count,
  })) ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Open Incidents"
          value={isLoading ? "-" : (stats?.incidents.open ?? 0)}
          icon={<AlertTriangle className="w-5 h-5" />}
          color="text-red-500"
        />
        <StatCard
          title="Open Groups"
          value={isLoading ? "-" : (stats?.cases.open ?? 0)}
          icon={<FolderOpen className="w-5 h-5" />}
          color="text-purple-500"
        />
        <StatCard
          title="Active Automations"
          value={isLoading ? "-" : (stats?.automations.active ?? 0)}
          icon={<Zap className="w-5 h-5" />}
          color="text-green-500"
        />
        <StatCard
          title="MTTR"
          value={stats?.incidents.mttr_hours != null ? `${stats.incidents.mttr_hours}h` : "N/A"}
          icon={<TrendingUp className="w-5 h-5" />}
          color="text-blue-500"
          subtitle="Mean time to resolve (30d)"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Daily trend */}
        <div className="md:col-span-2 border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-semibold text-sm mb-3">Incidents (Last 7 Days)</h2>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={dailyData}>
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-sm text-[var(--color-text-muted)]">
              No data yet
            </div>
          )}
        </div>

        {/* Severity distribution */}
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-semibold text-sm mb-3">By Severity</h2>
          {severityData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={severityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={70}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={false}
                >
                  {severityData.map((entry) => (
                    <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || "#6b7280"} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-sm text-[var(--color-text-muted)]">
              No data yet
            </div>
          )}
        </div>
      </div>

      {/* Status pipeline + Execution stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Status pipeline */}
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-semibold text-sm mb-3">Incident Pipeline</h2>
          <div className="space-y-2">
            {statusData.map(({ name, value }) => (
              <div key={name} className="flex items-center gap-2">
                <span className="w-24 text-xs text-right text-[var(--color-text-muted)]">{name}</span>
                <div className="flex-1 bg-[var(--color-surface-2)] rounded-full h-4 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.max(2, (value / Math.max(1, stats?.incidents.total ?? 1)) * 100)}%`,
                      backgroundColor: STATUS_COLORS[name] || "#6b7280",
                    }}
                  />
                </div>
                <span className="w-8 text-xs font-medium">{value}</span>
              </div>
            ))}
            {statusData.length === 0 && (
              <p className="text-sm text-[var(--color-text-muted)] text-center py-4">No data yet</p>
            )}
          </div>
        </div>

        {/* Execution stats */}
        <div className="border border-[var(--color-border)] rounded-lg p-4">
          <h2 className="font-semibold text-sm mb-3">Execution Stats</h2>
          <div className="grid grid-cols-2 gap-3">
            <MiniStat label="Total Runs" value={stats?.executions.total ?? 0} />
            <MiniStat
              label="Running"
              value={stats?.executions.running ?? 0}
              highlight={!!stats?.executions.running}
            />
            <MiniStat label="Completed" value={stats?.executions.completed ?? 0} />
            <MiniStat label="Failed" value={stats?.executions.failed ?? 0} warn />
            <MiniStat
              label="Avg Duration"
              value={
                stats?.executions.avg_duration_ms
                  ? `${(stats.executions.avg_duration_ms / 1000).toFixed(1)}s`
                  : "N/A"
              }
            />
          </div>
        </div>
      </div>

      {/* Recent activity */}
      <div className="border border-[var(--color-border)] rounded-lg">
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center gap-2">
          <Activity className="w-4 h-4" />
          <h2 className="font-semibold text-sm">Recent Activity</h2>
        </div>
        <div className="divide-y divide-[var(--color-border)]">
          {activity?.map((entry) => (
            <div key={entry.id} className="px-4 py-3 flex items-center gap-3">
              <span className="px-2 py-0.5 rounded text-xs bg-[var(--color-surface-2)]">
                {entry.entry_type.replace(/_/g, " ")}
              </span>
              <span className="flex-1 text-sm truncate">{entry.content}</span>
              <span className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDate(entry.created_at)}
              </span>
            </div>
          ))}
          {(!activity || activity.length === 0) && (
            <div className="px-4 py-8 text-center text-[var(--color-text-muted)]">
              No activity yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  color,
  subtitle,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}) {
  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-[var(--color-text-muted)]">{title}</span>
        <span className={color}>{icon}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      {subtitle && (
        <p className="text-xs text-[var(--color-text-muted)] mt-1">{subtitle}</p>
      )}
    </div>
  );
}

function MiniStat({
  label,
  value,
  highlight,
  warn,
}: {
  label: string;
  value: number | string;
  highlight?: boolean;
  warn?: boolean;
}) {
  return (
    <div className="p-2 rounded bg-[var(--color-surface-2)]">
      <p className="text-xs text-[var(--color-text-muted)]">{label}</p>
      <p className={`text-lg font-bold ${highlight ? "text-yellow-600" : warn ? "text-red-600" : ""}`}>
        {value}
      </p>
    </div>
  );
}
