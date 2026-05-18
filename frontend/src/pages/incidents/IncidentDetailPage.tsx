import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Clock } from "lucide-react";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { severityColors, statusColors, statusDotColors, formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { StartWorkButton } from "@/components/work/StartWorkButton";
import { WorkGateProvider, useWorkGate } from "@/components/work/WorkGateContext";
import { WorkGateBanner } from "@/components/work/WorkGateBanner";
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
import { AIActionsBar } from "@/components/ai/AIActionsBar";

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

  const { data: incident, isLoading } = useQuery({
    queryKey: ["incident", id],
    queryFn: () => api.get<Incident>(`/incidents/${id}`),
    enabled: !!id,
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

  return (
    <WorkGateProvider incidentId={id!}>
      <IncidentLayout incident={incident} />
    </WorkGateProvider>
  );
}

function IncidentLayout({ incident }: { incident: Incident }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get("tab") as TabId) || "overview";
  const setActiveTab = (tab: TabId) => {
    if (tab === "overview") setSearchParams({}, { replace: false });
    else setSearchParams({ tab }, { replace: false });
  };

  const { isWorking } = useWorkGate();

  const transition = useToastMutation({
    mutationFn: (newStatus: string) =>
      api.post(`/incidents/${incident.id}/transition`, { new_status: newStatus }),
    loadingMessage: "Updating status...",
    successMessage: "Status updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", incident.id] });
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", incident.id] });
    },
  });

  const available = nextStatuses[incident.status] || [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
      {/* ============ Sidebar ============ */}
      <aside className="space-y-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
          <button
            onClick={() => navigate(-1)}
            className="p-1 -ml-1 rounded hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text)] transition-colors"
            aria-label="Go back"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            onClick={() => navigate("/incidents")}
            className="hover:text-[var(--color-text)] transition-colors"
          >
            Incidents
          </button>
        </div>

        {/* Severity + status pills */}
        <div className="space-y-2">
          <SidebarLabel>Severity</SidebarLabel>
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold ${severityColors[incident.severity]}`}>
            {incident.severity}
          </span>
        </div>

        <div className="space-y-2">
          <SidebarLabel>Status</SidebarLabel>
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium ${statusColors[incident.status]}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${statusDotColors[incident.status]}`} />
            {incident.status.replace("_", " ")}
          </span>
        </div>

        {/* Start work — the gate. */}
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-2">
          <SidebarLabel>
            <Clock size={11} className="inline mr-1 -mt-0.5" /> Work session
          </SidebarLabel>
          <StartWorkButton incidentId={incident.id} />
          {!isWorking && (
            <p className="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
              Editing is locked until you start a work session on this incident.
            </p>
          )}
        </div>

        {/* Status transitions — gated */}
        {available.length > 0 && (
          <div className="space-y-2">
            <SidebarLabel>Transition to</SidebarLabel>
            <div className="flex flex-col gap-1.5">
              {available.map((status) => (
                <button
                  key={status}
                  onClick={() => transition.mutate(status)}
                  disabled={!isWorking || transition.isPending}
                  className="px-2.5 py-1.5 border border-[var(--color-border)] rounded text-xs text-left hover:bg-[var(--color-surface-2)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title={!isWorking ? "Start work to transition" : `Move to ${status.replace("_", " ")}`}
                >
                  Move to {status.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Source */}
        {incident.source && (
          <div className="space-y-2">
            <SidebarLabel>Source</SidebarLabel>
            <div className="text-xs text-[var(--color-text)]">
              {incident.source}
              {incident.source_ref && (
                <span className="block text-[var(--color-text-muted)] font-mono text-[10px] mt-0.5 break-all">
                  {incident.source_ref}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Lead */}
        {incident.lead && (
          <div className="space-y-2">
            <SidebarLabel>Lead</SidebarLabel>
            <div className="flex items-center gap-1.5 text-xs text-[var(--color-text)]">
              <UserAvatar displayName={incident.lead.display_name} size="sm" />
              {incident.lead.display_name}
            </div>
          </div>
        )}

        {/* Created by */}
        <div className="space-y-2">
          <SidebarLabel>Created by</SidebarLabel>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text)]">
            <UserAvatar displayName={incident.created_by.display_name} size="sm" />
            <div>
              <div>{incident.created_by.display_name}</div>
              <div className="text-[10px] text-[var(--color-text-muted)]">
                {formatDate(incident.created_at)}
              </div>
            </div>
          </div>
        </div>

        {/* Tags */}
        {incident.tags && incident.tags.length > 0 && (
          <div className="space-y-2">
            <SidebarLabel>Tags</SidebarLabel>
            <div className="flex flex-wrap gap-1">
              {incident.tags.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-[var(--color-surface-2)] text-[var(--color-text)]"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Assignments */}
        {incident.assignment_count > 0 && (
          <div className="space-y-2">
            <SidebarLabel>Assigned</SidebarLabel>
            <div className="text-xs text-[var(--color-text-muted)]">
              {incident.assignment_count} {incident.assignment_count === 1 ? "person" : "people"}
            </div>
          </div>
        )}

        {/* AI actions — auto-hides when no actions seeded for this page key */}
        <div className="pt-2 border-t border-[var(--color-border)]">
          <SidebarLabel>AI</SidebarLabel>
          <div className="mt-2">
            <AIActionsBar
              pageKey="incident_detail"
              context={{
                incident_id: incident.id,
                title: incident.title,
                severity: incident.severity,
                status: incident.status,
                tags: incident.tags,
              }}
            />
          </div>
        </div>
      </aside>

      {/* ============ Main workspace ============ */}
      <main className="min-w-0">
        {/* Title block */}
        <div className="mb-4">
          <h1 className="text-2xl font-semibold leading-tight text-[var(--color-text)]">
            {incident.title}
          </h1>
          {incident.summary && (
            <p className="mt-1.5 text-sm text-[var(--color-text-muted)]">
              {incident.summary}
            </p>
          )}
        </div>

        {/* Gate banner (read-only mode) */}
        <WorkGateBanner />

        {/* Tab bar */}
        <div className="border-b border-[var(--color-border)] mb-6">
          <nav className="flex gap-0 -mb-px overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
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
        {activeTab === "timeline" && <TimelineTab incidentId={incident.id} />}
        {activeTab === "chat" && <ChatTab incidentId={incident.id} />}
        {activeTab === "notes" && <NotesTab incidentId={incident.id} />}
        {activeTab === "files" && <FilesTab incidentId={incident.id} />}
        {activeTab === "forms" && <FormsTab incidentId={incident.id} />}
        {activeTab === "automations" && <AutomationsTab incidentId={incident.id} />}
        {activeTab === "variables" && <VariablesTab incidentId={incident.id} />}
        {activeTab === "issues" && (
          <EntityIssuesPanel
            targetType="incident"
            targetId={incident.id}
            targetName={incident.title}
          />
        )}
      </main>
    </div>
  );
}

function SidebarLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
      {children}
    </div>
  );
}

