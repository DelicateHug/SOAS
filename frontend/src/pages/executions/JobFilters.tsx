import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";
import type { PaginatedResponse, AutomationItem } from "@/types/api";

export interface JobFilterValues {
  enabled: string;
  automationId: string;
}

export const emptyJobFilters: JobFilterValues = {
  enabled: "",
  automationId: "",
};

interface Props {
  filters: JobFilterValues;
  onChange: (filters: JobFilterValues) => void;
}

const selectClass =
  "px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm bg-[hsl(var(--background))]";

export function JobFilters({ filters, onChange }: Props) {
  const { data: automationsData } = useQuery({
    queryKey: ["automations-filter-list"],
    queryFn: () =>
      api.get<PaginatedResponse<AutomationItem>>(
        "/automations?per_page=100"
      ),
    staleTime: 60_000,
  });

  const hasAnyFilter = filters.enabled || filters.automationId;

  return (
    <div className="flex flex-wrap gap-3 items-end">
      <div>
        <label className="block text-xs font-medium mb-1 text-[hsl(var(--muted-foreground))]">
          Status
        </label>
        <select
          value={filters.enabled}
          onChange={(e) => onChange({ ...filters, enabled: e.target.value })}
          className={selectClass}
        >
          <option value="">All Jobs</option>
          <option value="true">Enabled</option>
          <option value="false">Disabled</option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium mb-1 text-[hsl(var(--muted-foreground))]">
          Automation
        </label>
        <select
          value={filters.automationId}
          onChange={(e) =>
            onChange({ ...filters, automationId: e.target.value })
          }
          className={selectClass}
        >
          <option value="">All automations</option>
          {automationsData?.data.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>

      {hasAnyFilter && (
        <button
          onClick={() => onChange(emptyJobFilters)}
          className="flex items-center gap-1 px-3 py-1.5 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] border border-[hsl(var(--border))] rounded-md"
        >
          <X className="w-3 h-3" /> Clear
        </button>
      )}
    </div>
  );
}
