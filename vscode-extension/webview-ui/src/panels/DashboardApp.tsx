/**
 * Dashboard webview panel app.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface DashboardStats {
  incidents: { total: number; open: number; critical: number };
  cases: { total: number; open: number };
  automations: { total: number; active: number };
  executions: { total: number; running: number; failed_today: number };
}

interface ActivityItem {
  id: string;
  type: string;
  description: string;
  created_at: string;
  user?: { display_name: string };
}

export function DashboardApp() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.get<DashboardStats>("/dashboard/stats"),
  });

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ["dashboard-activity"],
    queryFn: () => api.get<{ data: ActivityItem[] }>("/dashboard/activity"),
  });

  return (
    <div style={{ padding: 24, color: "var(--vscode-foreground)", background: "var(--vscode-editor-background)", minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24 }}>Dashboard</h1>

      {/* Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginBottom: 32 }}>
        <StatCard
          title="Incidents"
          loading={statsLoading}
          items={[
            { label: "Total", value: stats?.incidents.total ?? 0 },
            { label: "Open", value: stats?.incidents.open ?? 0, color: "var(--vscode-charts-yellow)" },
            { label: "Critical", value: stats?.incidents.critical ?? 0, color: "var(--vscode-charts-red)" },
          ]}
        />
        <StatCard
          title="Cases"
          loading={statsLoading}
          items={[
            { label: "Total", value: stats?.cases.total ?? 0 },
            { label: "Open", value: stats?.cases.open ?? 0, color: "var(--vscode-charts-blue)" },
          ]}
        />
        <StatCard
          title="Automations"
          loading={statsLoading}
          items={[
            { label: "Total", value: stats?.automations.total ?? 0 },
            { label: "Active", value: stats?.automations.active ?? 0, color: "var(--vscode-charts-green)" },
          ]}
        />
        <StatCard
          title="Executions"
          loading={statsLoading}
          items={[
            { label: "Total", value: stats?.executions.total ?? 0 },
            { label: "Running", value: stats?.executions.running ?? 0, color: "var(--vscode-charts-blue)" },
            { label: "Failed Today", value: stats?.executions.failed_today ?? 0, color: "var(--vscode-charts-red)" },
          ]}
        />
      </div>

      {/* Recent Activity */}
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>Recent Activity</h2>
      {activityLoading ? (
        <p style={{ color: "var(--vscode-descriptionForeground)" }}>Loading activity...</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {activity?.data.map((item) => (
            <div
              key={item.id}
              style={{
                padding: "8px 12px",
                background: "var(--vscode-editor-inactiveSelectionBackground)",
                borderRadius: 4,
                fontSize: 13,
              }}
            >
              <span>{item.description}</span>
              <span style={{ float: "right", color: "var(--vscode-descriptionForeground)", fontSize: 11 }}>
                {item.user?.display_name} &middot; {new Date(item.created_at).toLocaleString()}
              </span>
            </div>
          )) ?? (
            <p style={{ color: "var(--vscode-descriptionForeground)" }}>No recent activity</p>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ title, loading, items }: {
  title: string;
  loading: boolean;
  items: Array<{ label: string; value: number; color?: string }>;
}) {
  return (
    <div style={{
      padding: 16,
      background: "var(--vscode-editor-inactiveSelectionBackground)",
      borderRadius: 8,
      border: "1px solid var(--vscode-panel-border)",
    }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: "var(--vscode-descriptionForeground)" }}>
        {title}
      </h3>
      {loading ? (
        <p style={{ color: "var(--vscode-descriptionForeground)" }}>Loading...</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {items.map((item) => (
            <div key={item.label} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span>{item.label}</span>
              <span style={{ fontWeight: 600, color: item.color }}>{item.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
