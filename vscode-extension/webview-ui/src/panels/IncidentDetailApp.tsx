/**
 * Incident detail webview panel app.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Incident {
  id: string;
  title: string;
  summary: string;
  severity: string;
  status: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  lead: { id: string; display_name: string } | null;
  assigned_count: number;
  metadata: Record<string, unknown>;
}

interface TimelineEntry {
  id: string;
  entry_type: string;
  content: string;
  created_at: string;
  created_by?: { display_name: string };
}

interface Note {
  id: string;
  content: string;
  created_at: string;
  created_by: { display_name: string };
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "var(--vscode-charts-red)",
  high: "var(--vscode-charts-orange)",
  medium: "var(--vscode-charts-yellow)",
  low: "var(--vscode-charts-blue)",
  informational: "var(--vscode-descriptionForeground)",
};

interface Props {
  incidentId: string;
}

type Tab = "overview" | "timeline" | "notes";

export function IncidentDetailApp({ incidentId }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const { data: incident, isLoading } = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => api.get<Incident>(`/incidents/${incidentId}`),
  });

  const { data: timeline } = useQuery({
    queryKey: ["incident-timeline", incidentId],
    queryFn: () => api.get<{ data: TimelineEntry[] }>(`/incidents/${incidentId}/timeline`),
    enabled: activeTab === "timeline",
  });

  const { data: notes } = useQuery({
    queryKey: ["incident-notes", incidentId],
    queryFn: () => api.get<{ data: Note[] }>(`/incidents/${incidentId}/notes`),
    enabled: activeTab === "notes",
  });

  if (isLoading || !incident) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--vscode-foreground)" }}>
        Loading incident...
      </div>
    );
  }

  const tabs: Tab[] = ["overview", "timeline", "notes"];

  return (
    <div style={{ color: "var(--vscode-foreground)", background: "var(--vscode-editor-background)", minHeight: "100vh" }}>
      {/* Header */}
      <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--vscode-panel-border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <span style={{
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: 12,
            fontWeight: 600,
            color: "#fff",
            background: SEVERITY_COLORS[incident.severity] || "#666",
          }}>
            {incident.severity.toUpperCase()}
          </span>
          <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)" }}>{incident.status}</span>
        </div>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{incident.title}</h1>
        {incident.summary && (
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--vscode-descriptionForeground)" }}>{incident.summary}</p>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--vscode-panel-border)", paddingLeft: 24 }}>
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 16px",
              background: "transparent",
              color: activeTab === tab ? "var(--vscode-foreground)" : "var(--vscode-descriptionForeground)",
              border: "none",
              borderBottom: activeTab === tab ? "2px solid var(--vscode-focusBorder)" : "2px solid transparent",
              cursor: "pointer",
              fontSize: 13,
              textTransform: "capitalize",
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{ padding: 24 }}>
        {activeTab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: "8px 16px", fontSize: 13 }}>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Lead</span>
            <span>{incident.lead?.display_name || "Unassigned"}</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Assigned</span>
            <span>{incident.assigned_count} user(s)</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Tags</span>
            <span>{incident.tags.join(", ") || "None"}</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Created</span>
            <span>{new Date(incident.created_at).toLocaleString()}</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Updated</span>
            <span>{new Date(incident.updated_at).toLocaleString()}</span>
          </div>
        )}

        {activeTab === "timeline" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {timeline?.data.map((entry) => (
              <div key={entry.id} style={{ padding: "8px 12px", background: "var(--vscode-editor-inactiveSelectionBackground)", borderRadius: 4, fontSize: 13 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontWeight: 500, textTransform: "capitalize" }}>{entry.entry_type.replace("_", " ")}</span>
                  <span style={{ fontSize: 11, color: "var(--vscode-descriptionForeground)" }}>
                    {entry.created_by?.display_name} &middot; {new Date(entry.created_at).toLocaleString()}
                  </span>
                </div>
                <span>{entry.content}</span>
              </div>
            )) ?? <p style={{ color: "var(--vscode-descriptionForeground)" }}>No timeline entries</p>}
          </div>
        )}

        {activeTab === "notes" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {notes?.data.map((note) => (
              <div key={note.id} style={{ padding: "8px 12px", background: "var(--vscode-editor-inactiveSelectionBackground)", borderRadius: 4, fontSize: 13 }}>
                <div style={{ fontSize: 11, color: "var(--vscode-descriptionForeground)", marginBottom: 4 }}>
                  {note.created_by.display_name} &middot; {new Date(note.created_at).toLocaleString()}
                </div>
                <div style={{ whiteSpace: "pre-wrap" }}>{note.content}</div>
              </div>
            )) ?? <p style={{ color: "var(--vscode-descriptionForeground)" }}>No notes</p>}
          </div>
        )}
      </div>
    </div>
  );
}
