import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { severityColors, statusColors, formatDate } from "@/lib/utils";
import { ChevronDown, ChevronRight, Layers } from "lucide-react";
import { AddToGroupPopover } from "./AddToGroupPopover";
import type { PaginatedResponse, IncidentGroupWithIncidents, IncidentListItem } from "@/types/api";

const priorityLabels: Record<number, string> = {
  1: "P1",
  2: "P2",
  3: "P3",
  4: "P4",
  5: "P5",
};

const statusBadgeColors: Record<string, string> = {
  open: "bg-green-100 text-green-800",
  investigating: "bg-blue-100 text-blue-800",
  pending: "bg-yellow-100 text-yellow-800",
  closed: "bg-gray-100 text-gray-800",
  archived: "bg-gray-100 text-gray-500",
};

export function IncidentGroupedView() {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [groupPopoverIncident, setGroupPopoverIncident] = useState<string | null>(null);

  const { data: groupsData, isLoading: groupsLoading } = useQuery({
    queryKey: ["incident-groups"],
    queryFn: () =>
      api.get<PaginatedResponse<IncidentGroupWithIncidents>>("/cases/grouped?per_page=50"),
  });

  // Also fetch all incidents to find ungrouped ones
  const { data: allIncidents } = useQuery({
    queryKey: ["incidents", { severity: "", status: "", page: 1 }],
    queryFn: () =>
      api.get<PaginatedResponse<IncidentListItem>>("/incidents?per_page=100"),
  });

  const groups = groupsData?.data ?? [];

  // Collect all incident IDs that belong to at least one group
  const groupedIncidentIds = new Set<string>();
  for (const group of groups) {
    for (const incident of group.incidents) {
      groupedIncidentIds.add(incident.id);
    }
  }

  // Ungrouped incidents
  const ungroupedIncidents = (allIncidents?.data ?? []).filter(
    (i) => !groupedIncidentIds.has(i.id)
  );

  const toggleGroup = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (groupsLoading) {
    return <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">Loading...</div>;
  }

  return (
    <div className="space-y-3">
      {groups.length === 0 && ungroupedIncidents.length === 0 && (
        <div className="flex flex-col items-center py-12 text-[hsl(var(--muted-foreground))]">
          <Layers className="w-12 h-12 mb-3" />
          <p>No groups or incidents yet</p>
        </div>
      )}

      {groups.map((group) => (
        <div
          key={group.id}
          className="border border-[hsl(var(--border))] rounded-lg overflow-hidden"
        >
          {/* Group header */}
          <button
            onClick={() => toggleGroup(group.id)}
            className="w-full flex items-center gap-3 px-4 py-3 bg-[hsl(var(--muted))] hover:bg-[hsl(var(--accent))] transition-colors text-left"
          >
            {expanded.has(group.id) ? (
              <ChevronDown className="w-4 h-4 shrink-0" />
            ) : (
              <ChevronRight className="w-4 h-4 shrink-0" />
            )}
            <Link
              to={`/cases/${group.id}`}
              onClick={(e) => e.stopPropagation()}
              className="font-medium text-sm hover:underline text-[hsl(var(--primary))]"
            >
              {group.title}
            </Link>
            <span
              className={`px-2 py-0.5 rounded text-xs ${
                statusBadgeColors[group.status] ?? "bg-gray-100 text-gray-800"
              }`}
            >
              {group.status}
            </span>
            <span className="text-xs text-[hsl(var(--muted-foreground))]">
              {priorityLabels[group.priority] ?? `P${group.priority}`}
            </span>
            <span className="ml-auto text-xs text-[hsl(var(--muted-foreground))]">
              {group.incidents.length} incident{group.incidents.length !== 1 ? "s" : ""}
            </span>
          </button>

          {/* Nested incidents table */}
          {expanded.has(group.id) && (
            <div>
              {group.incidents.length === 0 ? (
                <div className="px-4 py-4 text-sm text-[hsl(var(--muted-foreground))] text-center">
                  No incidents in this group
                </div>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="border-t border-b border-[hsl(var(--border))] bg-[hsl(var(--background))]">
                      <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))] pl-12">
                        Severity
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                        Status
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                        Title
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                        Lead
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                        Created
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                        Groups
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[hsl(var(--border))]">
                    {group.incidents.map((incident) => (
                      <IncidentRow
                        key={incident.id}
                        incident={incident}
                        indented
                        popoverOpen={groupPopoverIncident === incident.id}
                        onTogglePopover={() =>
                          setGroupPopoverIncident(
                            groupPopoverIncident === incident.id ? null : incident.id
                          )
                        }
                        onClosePopover={() => setGroupPopoverIncident(null)}
                      />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      ))}

      {/* Ungrouped incidents */}
      {ungroupedIncidents.length > 0 && (
        <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-[hsl(var(--muted))]">
            <span className="text-sm font-medium text-[hsl(var(--muted-foreground))]">
              Ungrouped Incidents ({ungroupedIncidents.length})
            </span>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-t border-b border-[hsl(var(--border))] bg-[hsl(var(--background))]">
                <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  Severity
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  Status
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  Title
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  Lead
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  Created
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">
                  Groups
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {ungroupedIncidents.map((incident) => (
                <IncidentRow
                  key={incident.id}
                  incident={incident}
                  popoverOpen={groupPopoverIncident === incident.id}
                  onTogglePopover={() =>
                    setGroupPopoverIncident(
                      groupPopoverIncident === incident.id ? null : incident.id
                    )
                  }
                  onClosePopover={() => setGroupPopoverIncident(null)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function IncidentRow({
  incident,
  indented,
  popoverOpen,
  onTogglePopover,
  onClosePopover,
}: {
  incident: IncidentListItem;
  indented?: boolean;
  popoverOpen: boolean;
  onTogglePopover: () => void;
  onClosePopover: () => void;
}) {
  return (
    <tr className="hover:bg-[hsl(var(--accent))]">
      <td className={`px-4 py-3 ${indented ? "pl-12" : ""}`}>
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${severityColors[incident.severity]}`}
        >
          {incident.severity}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className={`px-2 py-0.5 rounded text-xs ${statusColors[incident.status]}`}>
          {incident.status.replace("_", " ")}
        </span>
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/incidents/${incident.id}`}
          className="text-sm text-[hsl(var(--primary))] hover:underline"
        >
          {incident.title}
        </Link>
      </td>
      <td className="px-4 py-3 text-sm text-[hsl(var(--muted-foreground))]">
        {incident.lead?.display_name || "-"}
      </td>
      <td className="px-4 py-3 text-sm text-[hsl(var(--muted-foreground))]">
        {formatDate(incident.created_at)}
      </td>
      <td className="px-4 py-3 relative">
        <button
          onClick={onTogglePopover}
          className="flex items-center gap-1 px-2 py-1 text-xs border border-[hsl(var(--border))] rounded hover:bg-[hsl(var(--accent))]"
        >
          <Layers className="w-3 h-3" />
          {incident.group_ids?.length || 0}
        </button>
        {popoverOpen && (
          <AddToGroupPopover
            incidentId={incident.id}
            currentGroupIds={incident.group_ids || []}
            onClose={onClosePopover}
          />
        )}
      </td>
    </tr>
  );
}
