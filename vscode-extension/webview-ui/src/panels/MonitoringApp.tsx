/**
 * Monitoring webview panel app.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface ComponentHealth {
  name: string;
  status: string;
  message?: string;
  last_check: string;
}

interface MonitoringOverview {
  components: ComponentHealth[];
  alert_count: number;
  overall_status: string;
}

const STATUS_COLORS: Record<string, string> = {
  healthy: "var(--vscode-charts-green)",
  degraded: "var(--vscode-charts-yellow)",
  unhealthy: "var(--vscode-charts-red)",
  unknown: "var(--vscode-descriptionForeground)",
};

export function MonitoringApp() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["monitoring-overview"],
    queryFn: () => api.get<MonitoringOverview>("/monitoring/overview"),
    refetchInterval: 15_000,
  });

  return (
    <div style={{ padding: 24, color: "var(--vscode-foreground)", background: "var(--vscode-editor-background)", minHeight: "100vh" }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8 }}>System Monitoring</h1>

      {isLoading && <p>Loading monitoring data...</p>}
      {error && <p style={{ color: "var(--vscode-charts-red)" }}>Failed to load monitoring data</p>}

      {data && (
        <>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 16px",
            borderRadius: 20,
            marginBottom: 24,
            background: "var(--vscode-editor-inactiveSelectionBackground)",
            fontSize: 14,
          }}>
            <span style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: STATUS_COLORS[data.overall_status] || STATUS_COLORS.unknown,
            }} />
            <span style={{ fontWeight: 600, textTransform: "capitalize" }}>{data.overall_status}</span>
            {data.alert_count > 0 && (
              <span style={{ color: "var(--vscode-charts-red)" }}>
                ({data.alert_count} active alert{data.alert_count !== 1 ? "s" : ""})
              </span>
            )}
          </div>

          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>Components</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.components.map((comp) => (
              <div
                key={comp.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "10px 16px",
                  background: "var(--vscode-editor-inactiveSelectionBackground)",
                  borderRadius: 6,
                  border: "1px solid var(--vscode-panel-border)",
                }}
              >
                <span style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: STATUS_COLORS[comp.status] || STATUS_COLORS.unknown,
                  flexShrink: 0,
                }} />
                <span style={{ fontWeight: 500, minWidth: 120 }}>{comp.name}</span>
                <span style={{
                  fontSize: 12,
                  textTransform: "capitalize",
                  color: STATUS_COLORS[comp.status] || STATUS_COLORS.unknown,
                }}>
                  {comp.status}
                </span>
                {comp.message && (
                  <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)", marginLeft: "auto" }}>
                    {comp.message}
                  </span>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
