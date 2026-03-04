import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";
import type { PaginatedResponse, AutomationItem } from "@/types/api";

const executionStatuses = [
  "pending",
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
  "timed_out",
];

export interface ExecutionFilterValues {
  status: string;
  automationId: string;
  startedAfter: string;
  startedBefore: string;
}

export const emptyExecutionFilters: ExecutionFilterValues = {
  status: "",
  automationId: "",
  startedAfter: "",
  startedBefore: "",
};

interface Props {
  filters: ExecutionFilterValues;
  onChange: (filters: ExecutionFilterValues) => void;
}

const selectClass =
  "px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm bg-[hsl(var(--background))]";
const inputClass =
  "px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm bg-[hsl(var(--background))]";

export function ExecutionFilters({ filters, onChange }: Props) {
  const { data: automationsData } = useQuery({
    queryKey: ["automations-filter-list"],
    queryFn: () =>
      api.get<PaginatedResponse<AutomationItem>>(
        "/automations?per_page=100"
      ),
    staleTime: 60_000,
  });

  const hasAnyFilter =
    filters.status ||
    filters.automationId ||
    filters.startedAfter ||
    filters.startedBefore;

  return (
    <div className="flex flex-wrap gap-3 mb-4 items-end">
      <div>
        <label className="block text-xs font-medium mb-1 text-[hsl(var(--muted-foreground))]">
          Status
        </label>
        <select
          value={filters.status}
          onChange={(e) => onChange({ ...filters, status: e.target.value })}
          className={selectClass}
        >
          <option value="">All statuses</option>
          {executionStatuses.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
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

      <div>
        <label className="block text-xs font-medium mb-1 text-[hsl(var(--muted-foreground))]">
          Started After
        </label>
        <input
          type="datetime-local"
          value={filters.startedAfter}
          onChange={(e) =>
            onChange({ ...filters, startedAfter: e.target.value })
          }
          className={inputClass}
        />
      </div>

      <div>
        <label className="block text-xs font-medium mb-1 text-[hsl(var(--muted-foreground))]">
          Started Before
        </label>
        <input
          type="datetime-local"
          value={filters.startedBefore}
          onChange={(e) =>
            onChange({ ...filters, startedBefore: e.target.value })
          }
          className={inputClass}
        />
      </div>

      {hasAnyFilter && (
        <button
          onClick={() => onChange(emptyExecutionFilters)}
          className="flex items-center gap-1 px-3 py-1.5 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] border border-[hsl(var(--border))] rounded-md"
        >
          <X className="w-3 h-3" /> Clear
        </button>
      )}
    </div>
  );
}
