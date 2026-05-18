/**
 * Incident detail — single-column "hero card + tabs" layout that mirrors the
 * case-managment investigation page. NOT a sidebar layout. Tabs that show
 * sensitive case data are gated behind WorkGateContent so the analyst sees a
 * "Start work to view…" placeholder until they claim the item.
 *
 * Header card (xs-card equivalent):
 *   ┌────────────────────────────────────────────────────────────┐
 *   │ [status] [severity]  edit-status   ID·shortid              │
 *   │ <Title>                                                    │
 *   │                                Created · Source · Tags     │
 *   ├────────────────────────────────────────────────────────────┤
 *   │ Owner: avatar+name      Work session pill: Start/Stop      │
 *   └────────────────────────────────────────────────────────────┘
 *   [tabs]
 *   [tab content — gated by WorkGateContent when sensitive]
 */
import { useParams, useNavigate, useSearchParams, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { severityColors, statusColors, statusDotColors, formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { StartWorkButton } from "@/components/work/StartWorkButton";
import { WorkGateProvider, useWorkGate } from "@/components/work/WorkGateContext";
import { WorkGateContent } from "@/components/work/WorkGateContent";
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
  { id: "overview", label: "Overview", gated: true },
  { id: "timeline", label: "Timeline", gated: false },
  { id: "chat", label: "Chat", gated: false },
  { id: "notes", label: "Notes", gated: true },
  { id: "files", label: "Files", gated: true },
  { id: "forms", label: "Forms", gated: true },
  { id: "automations", label: "Automations", gated: true },
  { id: "variables", label: "Variables", gated: true },
  { id: "issues", label: "Issues", gated: false },
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
  const shortId = incident.id.slice(0, 8);
  const activeTabSpec = tabs.find((t) => t.id === activeTab);

  return (
    <div className="max-w-7xl space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
        <button
          onClick={() => navigate(-1)}
          className="p-1 -ml-1 rounded hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text)]"
          aria-label="Go back"
        >
          <ChevronLeft size={14} />
        </button>
        <Link to="/incidents" className="hover:text-[var(--color-text)]">
          Incidents
        </Link>
      </div>

      {/* ============ Hero card ============ */}
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
        {/* Top: badges + title + metrics */}
        <div className="px-5 py-4 flex items-start justify-between flex-wrap gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold ${severityColors[incident.severity]}`}>
                {incident.severity}
              </span>
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${statusColors[incident.status]}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${statusDotColors[incident.status]}`} />
                {incident.status.replace("_", " ")}
              </span>
              {available.length > 0 && isWorking && (
                <div className="flex items-center gap-1 ml-1">
                  {available.map((status) => (
                    <button
                      key={status}
                      onClick={() => transition.mutate(status)}
                      disabled={transition.isPending}
                      className="px-2 py-0.5 border border-[var(--color-border)] rounded text-[11px] hover:bg-[var(--color-surface-2)] disabled:opacity-50"
                    >
                      → {status.replace("_", " ")}
                    </button>
                  ))}
                </div>
              )}
              <span className="ml-auto font-mono text-[11px] text-[var(--color-text-muted)]">
                {shortId}
              </span>
            </div>
            <h1 className="text-lg font-semibold leading-tight text-[var(--color-text)] truncate">
              {incident.title}
            </h1>
            {incident.summary && (
              <p className="mt-1 text-xs text-[var(--color-text-muted)] line-clamp-2">
                {incident.summary}
              </p>
            )}
          </div>

          {/* Metrics block */}
          <div className="flex items-start gap-6 flex-wrap">
            <Metric label="Detected" value={formatDate(incident.detected_at || incident.created_at)} />
            <Metric label="Source" value={incident.source || "—"} />
            <Metric label="Assigned" value={String(incident.assignment_count)} />
            {incident.tags && incident.tags.length > 0 && (
              <div className="min-w-[140px]">
                <Label>Tags</Label>
                <div className="flex flex-wrap gap-1 mt-0.5">
                  {incident.tags.slice(0, 4).map((t) => (
                    <span
                      key={t}
                      className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-[var(--color-surface-2)] text-[var(--color-text)]"
                    >
                      {t}
                    </span>
                  ))}
                  {incident.tags.length > 4 && (
                    <span className="text-[10px] text-[var(--color-text-muted)]">+{incident.tags.length - 4}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer: owner + work session pill */}
        <div className="px-5 py-3 bg-[var(--color-surface-2)] border-t border-[var(--color-border)] flex items-center gap-3 flex-wrap">
          <Label>Created by</Label>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text)]">
            <UserAvatar displayName={incident.created_by.display_name} size="sm" />
            {incident.created_by.display_name}
          </div>
          {incident.lead && (
            <>
              <span className="text-[var(--color-text-muted)] text-xs">·</span>
              <Label>Lead</Label>
              <div className="flex items-center gap-1.5 text-xs text-[var(--color-text)]">
                <UserAvatar displayName={incident.lead.display_name} size="sm" />
                {incident.lead.display_name}
              </div>
            </>
          )}
          <div className="ml-auto flex items-center gap-3">
            <StartWorkButton incidentId={incident.id} size="sm" />
          </div>
        </div>
      </div>

      {/* AI actions row, just under the hero — matches case-mgmt's analyst toolbar */}
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

      {/* ============ Tabs ============ */}
      <div className="border-b border-[var(--color-border)]">
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

      {/* ============ Tab content (gated when the tab is marked sensitive) ============ */}
      <div>
        {activeTabSpec?.gated ? (
          <WorkGateContent
            title="Start work to view incident data"
            subtitle="Overview, notes, files, and automations are hidden until you claim this incident. Timeline, chat, and issues remain available."
          >
            <TabContent tab={activeTab} incident={incident} />
          </WorkGateContent>
        ) : (
          <TabContent tab={activeTab} incident={incident} />
        )}
      </div>
    </div>
  );
}

function TabContent({ tab, incident }: { tab: TabId; incident: Incident }) {
  switch (tab) {
    case "overview":   return <OverviewTab incident={incident} />;
    case "timeline":   return <TimelineTab incidentId={incident.id} />;
    case "chat":       return <ChatTab incidentId={incident.id} />;
    case "notes":      return <NotesTab incidentId={incident.id} />;
    case "files":      return <FilesTab incidentId={incident.id} />;
    case "forms":      return <FormsTab incidentId={incident.id} />;
    case "automations":return <AutomationsTab incidentId={incident.id} />;
    case "variables":  return <VariablesTab incidentId={incident.id} />;
    case "issues":     return <EntityIssuesPanel targetType="incident" targetId={incident.id} targetName={incident.title} />;
  }
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
      {children}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-[110px]">
      <Label>{label}</Label>
      <div className="text-xs text-[var(--color-text)] font-medium tabular-nums mt-0.5 truncate">
        {value}
      </div>
    </div>
  );
}
