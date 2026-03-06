import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import {
  formatDate,
  severityColors,
  statusColors,
  statusDotColors,
} from "@/lib/utils";
import { Unlink, Plus } from "lucide-react";
import { UserAvatar } from "@/components/ui/UserAvatar";
import type {
  CaseItem,
  IncidentListItem,
  PaginatedResponse,
} from "@/types/api";

interface Props {
  caseData: CaseItem;
  caseId: string;
}

export function OverviewTab({ caseData, caseId }: Props) {
  const queryClient = useQueryClient();
  const [showLinkPopover, setShowLinkPopover] = useState(false);

  const unlinkIncident = useToastMutation({
    mutationFn: (incidentId: string) =>
      api.delete(`/cases/${caseId}/incidents/${incidentId}`),
    loadingMessage: "Unlinking incident...",
    successMessage: "Incident unlinked.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });

  const linkIncident = useToastMutation({
    mutationFn: (incidentId: string) =>
      api.post(`/cases/${caseId}/incidents`, { incident_id: incidentId }),
    loadingMessage: "Linking incident...",
    successMessage: "Incident linked.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });

  const linkedIncidentIds = new Set(
    caseData.incidents.map((inc) => inc.id)
  );

  return (
    <div className="space-y-6">
      {/* Linked Incidents */}
      <div className="border border-[hsl(var(--border))] rounded-lg">
        <div className="px-4 py-3 border-b border-[hsl(var(--border))] flex items-center justify-between">
          <h2 className="font-semibold">
            Linked Incidents ({caseData.incidents.length})
          </h2>
          <div className="relative">
            <button
              onClick={() => setShowLinkPopover(!showLinkPopover)}
              className="flex items-center gap-1 px-2 py-1 text-xs border border-[hsl(var(--border))] rounded hover:bg-[hsl(var(--accent))] transition-colors"
            >
              <Plus className="w-3 h-3" />
              Link Incident
            </button>
            {showLinkPopover && (
              <LinkIncidentPopover
                linkedIds={linkedIncidentIds}
                onLink={(incId) => linkIncident.mutate(incId)}
                onUnlink={(incId) => unlinkIncident.mutate(incId)}
                onClose={() => setShowLinkPopover(false)}
                isPending={linkIncident.isPending || unlinkIncident.isPending}
              />
            )}
          </div>
        </div>

        {caseData.incidents.length === 0 ? (
          <div className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
            No incidents linked to this group
          </div>
        ) : (
          <div className="divide-y divide-[hsl(var(--border))]">
            {caseData.incidents.map((incident) => (
              <IncidentCard
                key={incident.id}
                incident={incident}
                onUnlink={() => unlinkIncident.mutate(incident.id)}
                unlinking={unlinkIncident.isPending}
              />
            ))}
          </div>
        )}
      </div>

      {/* Metadata */}
      {caseData.tags.length > 0 && (
        <div className="border border-[hsl(var(--border))] rounded-lg p-4">
          <h3 className="text-sm font-semibold mb-2">Tags</h3>
          <div className="flex gap-1 flex-wrap">
            {caseData.tags.map((tag) => (
              <span
                key={tag}
                className="px-1.5 py-0.5 rounded bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Timestamps */}
      <div className="border border-[hsl(var(--border))] rounded-lg p-4">
        <h3 className="text-sm font-semibold mb-2">Timestamps</h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-[hsl(var(--muted-foreground))]">Created:</span>{" "}
            {formatDate(caseData.created_at)}
          </div>
          <div>
            <span className="text-[hsl(var(--muted-foreground))]">Updated:</span>{" "}
            {formatDate(caseData.updated_at)}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Sub-components ---- */

function IncidentCard({
  incident,
  onUnlink,
  unlinking,
}: {
  incident: IncidentListItem;
  onUnlink: () => void;
  unlinking: boolean;
}) {
  return (
    <div className="px-4 py-3 flex items-center gap-3 hover:bg-[hsl(var(--accent)/0.3)] transition-colors group">
      <div className="flex-1 min-w-0">
        <Link
          to={`/incidents/${incident.id}`}
          className="text-sm font-medium hover:text-[hsl(var(--primary))] transition-colors"
        >
          {incident.title}
        </Link>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span
            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${severityColors[incident.severity]}`}
          >
            {incident.severity}
          </span>
          <span
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${statusColors[incident.status]}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${statusDotColors[incident.status] || ""}`}
            />
            {incident.status.replace("_", " ")}
          </span>
          {incident.lead && (
            <span className="text-[10px] text-[hsl(var(--muted-foreground))] flex items-center gap-1">
              <UserAvatar
                displayName={incident.lead.display_name}
                size="sm"
              />
              {incident.lead.display_name}
            </span>
          )}
          {incident.detected_at && (
            <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
              Detected {formatDate(incident.detected_at)}
            </span>
          )}
          {incident.tags.length > 0 && (
            <div className="flex gap-1">
              {incident.tags.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="px-1 py-0.5 rounded bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] text-[10px]"
                >
                  {tag}
                </span>
              ))}
              {incident.tags.length > 3 && (
                <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                  +{incident.tags.length - 3}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      <button
        onClick={onUnlink}
        disabled={unlinking}
        className="p-1.5 rounded text-[hsl(var(--muted-foreground))] hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
        title="Unlink incident"
      >
        <Unlink className="w-4 h-4" />
      </button>
    </div>
  );
}

function LinkIncidentPopover({
  linkedIds,
  onLink,
  onUnlink,
  onClose,
  isPending,
}: {
  linkedIds: Set<string>;
  onLink: (id: string) => void;
  onUnlink: (id: string) => void;
  onClose: () => void;
  isPending: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const { data: incidents, isLoading } = useQuery({
    queryKey: ["all-incidents-for-link"],
    queryFn: () =>
      api.get<PaginatedResponse<IncidentListItem>>(
        "/incidents?per_page=50&status=detected&status=triaging&status=investigating&status=containing&status=remediating"
      ),
  });

  return (
    <div
      ref={ref}
      className="absolute right-0 top-full mt-1 z-50 w-80 border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg"
    >
      <div className="px-3 py-2 border-b border-[hsl(var(--border))]">
        <p className="text-xs font-medium text-[hsl(var(--muted-foreground))]">
          Link incidents
        </p>
      </div>
      <div className="max-h-64 overflow-y-auto py-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="h-4 w-4 border-2 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !incidents?.data.length ? (
          <p className="px-3 py-2 text-xs text-[hsl(var(--muted-foreground))]">
            No open incidents found
          </p>
        ) : (
          incidents.data.map((inc) => {
            const isLinked = linkedIds.has(inc.id);
            return (
              <button
                key={inc.id}
                onClick={() =>
                  isLinked ? onUnlink(inc.id) : onLink(inc.id)
                }
                disabled={isPending}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[hsl(var(--accent))] disabled:opacity-50 text-left"
              >
                <input
                  type="checkbox"
                  checked={isLinked}
                  readOnly
                  className="rounded border-[hsl(var(--input))]"
                />
                <span className="flex-1 truncate">{inc.title}</span>
                <span
                  className={`px-1 py-0.5 rounded text-[10px] ${severityColors[inc.severity]}`}
                >
                  {inc.severity}
                </span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
