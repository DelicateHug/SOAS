import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { severityColors, statusColors, formatDate } from "@/lib/utils";
import { Plus, List, Layers, FolderPlus } from "lucide-react";
import { ProductionGuard } from "@/components/ui/ProductionGuard";
import { IncidentGroupedView } from "./IncidentGroupedView";
import { CreateGroupModal } from "./CreateGroupModal";
import { AddToGroupPopover } from "./AddToGroupPopover";
import type { PaginatedResponse, IncidentListItem, IncidentSeverity, IncidentStatus } from "@/types/api";
import { useTeamStore } from "@/stores/teamStore";

const severities: IncidentSeverity[] = ["critical", "high", "medium", "low", "informational"];
const statuses: IncidentStatus[] = [
  "detected", "triaging", "investigating", "containing",
  "remediating", "resolved", "closed", "false_positive",
];

export function IncidentListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const viewMode = (searchParams.get("view") as "flat" | "grouped") || "flat";
  const [filters, setFilters] = useState({ severity: "", status: "", page: 1 });
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [groupPopoverIncident, setGroupPopoverIncident] = useState<string | null>(null);
  const activeTeamId = useTeamStore((s) => s.activeTeamId);

  const setView = (view: "flat" | "grouped") => {
    const params = new URLSearchParams(searchParams);
    if (view === "flat") {
      params.delete("view");
    } else {
      params.set("view", view);
    }
    setSearchParams(params);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["incidents", filters, activeTeamId],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.severity) params.set("severity", filters.severity);
      if (filters.status) params.set("status", filters.status);
      params.set("team_id", activeTeamId!);
      params.set("page", String(filters.page));
      params.set("per_page", "25");
      return api.get<PaginatedResponse<IncidentListItem>>(`/incidents?${params}`);
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Incidents</h1>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex items-center border border-[hsl(var(--border))] rounded-md p-0.5">
            <button
              onClick={() => setView("flat")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
                viewMode === "flat"
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                  : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              }`}
            >
              <List className="w-4 h-4" /> Ungrouped
            </button>
            <button
              onClick={() => setView("grouped")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors ${
                viewMode === "grouped"
                  ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                  : "text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              }`}
            >
              <Layers className="w-4 h-4" /> Grouped
            </button>
          </div>

          {viewMode === "grouped" && (
            <ProductionGuard>
              <button
                onClick={() => setShowCreateGroup(true)}
                className="flex items-center gap-2 px-4 py-2 border border-[hsl(var(--border))] rounded-md text-sm hover:bg-[hsl(var(--accent))]"
              >
                <FolderPlus className="w-4 h-4" /> New Group
              </button>
            </ProductionGuard>
          )}

          <ProductionGuard>
            <Link
              to="/incidents/new"
              className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm hover:opacity-90"
            >
              <Plus className="w-4 h-4" /> New Incident
            </Link>
          </ProductionGuard>
        </div>
      </div>

      {viewMode === "flat" ? (
        <>
          {/* Filters */}
          <div className="flex gap-3 mb-4">
            <select
              value={filters.severity}
              onChange={(e) => setFilters({ ...filters, severity: e.target.value, page: 1 })}
              className="px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
            >
              <option value="">All Severities</option>
              {severities.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value, page: 1 })}
              className="px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
            >
              <option value="">All Statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>{s.replace("_", " ")}</option>
              ))}
            </select>
          </div>

          {/* Table */}
          <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
                  <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Severity</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Title</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Lead</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Created</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-[hsl(var(--muted-foreground))]">Groups</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[hsl(var(--border))]">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      Loading...
                    </td>
                  </tr>
                ) : data?.data.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[hsl(var(--muted-foreground))]">
                      No incidents found
                    </td>
                  </tr>
                ) : (
                  data?.data.map((incident) => (
                    <tr key={incident.id} className="hover:bg-[hsl(var(--accent))]">
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColors[incident.severity]}`}>
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
                          onClick={() =>
                            setGroupPopoverIncident(
                              groupPopoverIncident === incident.id ? null : incident.id
                            )
                          }
                          className="flex items-center gap-1 px-2 py-1 text-xs border border-[hsl(var(--border))] rounded hover:bg-[hsl(var(--accent))]"
                        >
                          <Layers className="w-3 h-3" />
                          {incident.group_ids?.length || 0}
                        </button>
                        {groupPopoverIncident === incident.id && (
                          <AddToGroupPopover
                            incidentId={incident.id}
                            currentGroupIds={incident.group_ids || []}
                            onClose={() => setGroupPopoverIncident(null)}
                          />
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data && data.meta.total_pages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              {Array.from({ length: data.meta.total_pages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => setFilters({ ...filters, page })}
                  className={`px-3 py-1 rounded text-sm ${
                    page === filters.page
                      ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                      : "border border-[hsl(var(--border))]"
                  }`}
                >
                  {page}
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        <IncidentGroupedView />
      )}

      {showCreateGroup && (
        <CreateGroupModal onClose={() => setShowCreateGroup(false)} />
      )}
    </div>
  );
}
