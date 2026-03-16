/**
 * Case detail webview panel app.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface CaseDetail {
  id: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  incident_count: number;
  tags: string[];
  created_at: string;
  updated_at: string;
  lead: { id: string; display_name: string } | null;
}

interface IncidentBrief {
  id: string;
  title: string;
  severity: string;
  status: string;
}

interface Note {
  id: string;
  content: string;
  created_at: string;
  created_by: { display_name: string };
}

interface Props {
  caseId: string;
}

type Tab = "overview" | "incidents" | "notes";

export function CaseDetailApp({ caseId }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");

  const { data: caseDetail, isLoading } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => api.get<CaseDetail>(`/cases/${caseId}`),
  });

  const { data: notes } = useQuery({
    queryKey: ["case-notes", caseId],
    queryFn: () => api.get<{ data: Note[] }>(`/cases/${caseId}/notes`),
    enabled: activeTab === "notes",
  });

  if (isLoading || !caseDetail) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--vscode-foreground)" }}>
        Loading case...
      </div>
    );
  }

  const tabs: Tab[] = ["overview", "incidents", "notes"];

  return (
    <div style={{ color: "var(--vscode-foreground)", background: "var(--vscode-editor-background)", minHeight: "100vh" }}>
      <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--vscode-panel-border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <span style={{ padding: "2px 8px", borderRadius: 4, fontSize: 12, fontWeight: 600, background: "var(--vscode-badge-background)", color: "var(--vscode-badge-foreground)" }}>
            {caseDetail.priority.toUpperCase()}
          </span>
          <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)" }}>{caseDetail.status}</span>
          <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)" }}>{caseDetail.incident_count} incidents</span>
        </div>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>{caseDetail.title}</h1>
        {caseDetail.description && (
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--vscode-descriptionForeground)" }}>{caseDetail.description}</p>
        )}
      </div>

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

      <div style={{ padding: 24 }}>
        {activeTab === "overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: "8px 16px", fontSize: 13 }}>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Lead</span>
            <span>{caseDetail.lead?.display_name || "Unassigned"}</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Tags</span>
            <span>{caseDetail.tags.join(", ") || "None"}</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Created</span>
            <span>{new Date(caseDetail.created_at).toLocaleString()}</span>
            <span style={{ color: "var(--vscode-descriptionForeground)" }}>Updated</span>
            <span>{new Date(caseDetail.updated_at).toLocaleString()}</span>
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
