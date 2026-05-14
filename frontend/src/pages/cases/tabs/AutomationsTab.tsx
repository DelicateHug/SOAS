import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { useTeamStore } from "@/stores/teamStore";
import { formatDate, formatDuration } from "@/lib/utils";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type {
  AutomationItem,
  IncidentAutomationExecution,
  PaginatedResponse,
} from "@/types/api";

interface Props {
  caseId: string;
}

const statusBadge: Record<string, string> = {
  pending: "bg-gray-500/20 text-gray-400",
  queued: "bg-blue-500/20 text-blue-400",
  running: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-green-500/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-500/20 text-gray-400",
  timed_out: "bg-orange-500/20 text-orange-400",
};

export function AutomationsTab({ caseId }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedAutomation, setSelectedAutomation] = useState("");

  const { data: executions } = useQuery({
    queryKey: ["case-automations", caseId],
    queryFn: () =>
      api.get<IncidentAutomationExecution[]>(`/cases/${caseId}/automations`),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.some((e) => e.status === "running" || e.status === "queued") ? 5000 : false;
    },
  });

  const { data: pendingInputData } = useQuery({
    queryKey: ["pending-input"],
    queryFn: () => api.get<{ execution_ids: string[] }>("/executions/pending-input"),
    refetchInterval: () => {
      const hasActive = executions?.some(
        (e) => e.status === "running" || e.status === "queued"
      );
      return hasActive ? 5000 : false;
    },
  });
  const pendingInputIds = new Set(pendingInputData?.execution_ids || []);

  const activeTeamId = useTeamStore((s) => s.activeTeamId);
  const { data: automations } = useQuery({
    queryKey: ["automations-active", activeTeamId],
    queryFn: () =>
      api.get<PaginatedResponse<AutomationItem>>(`/automations?status=active&per_page=100&team_id=${activeTeamId}`),
    enabled: !!activeTeamId,
  });

  const runAutomation = useToastMutation({
    mutationFn: (automationId: string) =>
      api.post(`/cases/${caseId}/automations/${automationId}/run`),
    loadingMessage: "Running automation...",
    successMessage: "Automation started.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-automations", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      setSelectedAutomation("");
    },
  });

  const toggleEvidence = useToastMutation({
    mutationFn: (executionId: string) =>
      api.post(`/cases/${caseId}/automations/${executionId}/evidence`),
    loadingMessage: "Updating evidence...",
    successMessage: "Evidence updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-automations", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
    },
  });

  const activeAutomations = automations?.data || [];

  return (
    <div className="space-y-6">
      {/* Manual run */}
      <div className="rounded-lg border border-[var(--color-border)] p-4">
        <SectionHeader title="Run Automation" />
        <div className="flex gap-2">
          <select
            value={selectedAutomation}
            onChange={(e) => setSelectedAutomation(e.target.value)}
            className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-[var(--color-bg)] text-[var(--color-text)]"
          >
            <option value="">Select an automation...</option>
            {activeAutomations.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => selectedAutomation && runAutomation.mutate(selectedAutomation)}
            disabled={!selectedAutomation || runAutomation.isPending}
            className="px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm disabled:opacity-50"
          >
            {runAutomation.isPending ? "Running..." : "Run"}
          </button>
        </div>
      </div>

      {/* Execution history */}
      <div>
        <SectionHeader title="Execution History" />
        <div className="space-y-2">
          {executions?.map((ex) => (
            <div
              key={ex.id}
              onClick={() => navigate(`/executions/${ex.id}`)}
              className="rounded-lg border border-[var(--color-border)] px-4 py-3 cursor-pointer hover:bg-[var(--color-surface-2)] transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{ex.automation_name}</span>
                <span
                  className={`text-xs px-1.5 py-0.5 rounded ${statusBadge[ex.status] || ""}`}
                >
                  {ex.status}
                </span>
                {ex.is_evidence && (
                  <span className="px-1.5 py-0.5 rounded text-xs bg-amber-500/20 text-amber-400">
                    evidence
                  </span>
                )}
                {pendingInputIds.has(ex.id) && (
                  <span className="px-1.5 py-0.5 rounded text-xs bg-yellow-500/20 text-yellow-400 animate-pulse">
                    Input needed
                  </span>
                )}
                {ex.duration_ms != null && (
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {formatDuration(ex.duration_ms)}
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleEvidence.mutate(ex.id);
                  }}
                  title={ex.is_evidence ? "Unmark as evidence" : "Mark as evidence"}
                  className={`ml-auto p-1 rounded text-xs transition-colors ${
                    ex.is_evidence
                      ? "text-amber-400 hover:bg-amber-500/20"
                      : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)]"
                  }`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill={ex.is_evidence ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                </button>
                <span className="text-xs text-[var(--color-text-muted)]">
                  {ex.created_at ? formatDate(ex.created_at) : ""}
                </span>
              </div>
              {ex.parameters && Object.keys(ex.parameters).length > 0 && (
                <div className="mt-1 text-xs text-[var(--color-text-muted)]">
                  {ex.parameters.manual_run
                    ? "Manual run"
                    : ex.parameters.trigger_tags
                      ? `Triggered by tags: ${(ex.parameters.trigger_tags as string[]).join(", ")}`
                      : ex.parameters.trigger_source
                        ? "Triggered by source"
                        : ""}
                </div>
              )}
            </div>
          ))}
          {(!executions || executions.length === 0) && (
            <div className="py-8 text-center text-[var(--color-text-muted)]">
              No automations have run on this case
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
