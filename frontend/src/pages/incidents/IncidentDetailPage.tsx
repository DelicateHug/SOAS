import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { severityColors, statusColors, statusDotColors, formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import type { Incident } from "@/types/api";
import { OverviewTab } from "./tabs/OverviewTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { NotesTab } from "./tabs/NotesTab";
import { FilesTab } from "./tabs/FilesTab";
import { AutomationsTab } from "./tabs/AutomationsTab";
import { ChatTab } from "./tabs/ChatTab";
import { VariablesTab } from "./tabs/VariablesTab";
import { FormsTab } from "./tabs/FormsTab";
import { EntityIssuesPanel } from "@/components/issues/EntityIssuesPanel";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "timeline", label: "Timeline" },
  { id: "chat", label: "Chat" },
  { id: "notes", label: "Notes" },
  { id: "files", label: "Files" },
  { id: "forms", label: "Forms" },
  { id: "automations", label: "Automations" },
  { id: "variables", label: "Variables" },
  { id: "issues", label: "Issues" },
] as const;

type TabId = (typeof tabs)[number]["id"];

const nextStatuses: Record<string, string[]> = {
  detected: ["triaging", "false_positive"],
  triaging: ["investigating", "false_positive"],
  investigating: ["containing", "remediating"],
  containing: ["remediating"],
  remediating: ["resolved"],
  resolved: ["closed"],
};

export function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get("tab") as TabId) || "overview";
  const setActiveTab = (tab: TabId) => {
    if (tab === "overview") {
      setSearchParams({}, { replace: false });
    } else {
      setSearchParams({ tab }, { replace: false });
    }
  };

  const { data: incident, isLoading } = useQuery({
    queryKey: ["incident", id],
    queryFn: () => api.get<Incident>(`/incidents/${id}`),
    enabled: !!id,
  });

  const transition = useToastMutation({
    mutationFn: (newStatus: string) =>
      api.post(`/incidents/${id}/transition`, { new_status: newStatus }),
    loadingMessage: "Updating status...",
    successMessage: "Status updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", id] });
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", id] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="text-center py-16">
        <p className="text-[var(--color-text-muted)]">Incident not found</p>
        <button
          onClick={() => navigate("/incidents")}
          className="mt-3 text-sm text-[var(--color-primary)] hover:underline"
        >
          Back to incidents
        </button>
      </div>
    );
  }

  const available = nextStatuses[incident.status] || [];

  return (
    <div className="max-w-6xl">
      {/* Header */}
      <div className="mb-6">
        {/* Breadcrumb + actions row */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(-1)}
              className="p-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              aria-label="Go back"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
            </button>
            <button
              onClick={() => navigate("/incidents")}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            >
              Incidents /
            </button>
          </div>

          {/* Status transition buttons */}
          {available.length > 0 && (
            <div className="flex gap-2">
              {available.map((status) => (
                <button
                  key={status}
                  onClick={() => transition.mutate(status)}
                  disabled={transition.isPending}
                  className="px-3 py-1.5 border border-[var(--color-border)] rounded-md text-xs font-medium hover:bg-[var(--color-surface-2)] transition-colors disabled:opacity-50"
                >
                  Move to {status.replace("_", " ")}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Title + badges */}
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold leading-tight mb-2">{incident.title}</h1>
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${severityColors[incident.severity]}`}>
                {incident.severity}
              </span>
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${statusColors[incident.status]}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${statusDotColors[incident.status]}`} />
                {incident.status.replace("_", " ")}
              </span>
              {incident.source && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
                  {incident.source}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-4 mt-3 text-xs text-[var(--color-text-muted)]">
          <div className="flex items-center gap-1.5">
            <UserAvatar displayName={incident.created_by.display_name} size="sm" />
            <span>{incident.created_by.display_name}</span>
          </div>
          <span>{formatDate(incident.created_at)}</span>
          {incident.lead && (
            <div className="flex items-center gap-1.5">
              <span className="text-[var(--color-text-muted)]">Lead:</span>
              <UserAvatar displayName={incident.lead.display_name} size="sm" />
              <span>{incident.lead.display_name}</span>
            </div>
          )}
          {incident.assignment_count > 0 && (
            <span>{incident.assignment_count} assigned</span>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="border-b border-[var(--color-border)] mb-6">
        <nav className="flex gap-0 -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-[var(--color-primary)] text-[var(--color-text)]"
                  : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-border)]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewTab incident={incident} />}
      {activeTab === "timeline" && <TimelineTab incidentId={id!} />}
      {activeTab === "chat" && <ChatTab incidentId={id!} />}
      {activeTab === "notes" && <NotesTab incidentId={id!} />}
      {activeTab === "files" && <FilesTab incidentId={id!} />}
      {activeTab === "forms" && <FormsTab incidentId={id!} />}
      {activeTab === "automations" && <AutomationsTab incidentId={id!} />}
      {activeTab === "variables" && <VariablesTab incidentId={id!} />}
      {activeTab === "issues" && (
        <EntityIssuesPanel
          targetType="incident"
          targetId={id!}
          targetName={incident?.title ?? ""}
        />
      )}
    </div>
  );
}
