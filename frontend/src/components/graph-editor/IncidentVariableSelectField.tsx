/**
 * Dropdown field for selecting an incident variable in Get/Set Incident Var nodes.
 * Fetches available incident variable definitions from the API with type-ahead filtering.
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

interface IncidentVariable {
  id: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
}

interface PaginatedResponse {
  data: IncidentVariable[];
  meta: { total: number };
}

interface IncidentVariableSelectFieldProps {
  value: string;
  onChange: (variableName: string) => void;
}

export function IncidentVariableSelectField({ value, onChange }: IncidentVariableSelectFieldProps) {
  const [filter, setFilter] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const { data: response, isLoading } = useQuery({
    queryKey: ["incident-variables", "list"],
    queryFn: () => api.get<PaginatedResponse>("/incident-variables?per_page=100"),
    staleTime: 30_000,
  });

  const variables = useMemo(() => {
    const items = response?.data || [];
    if (!filter) return items;
    const lower = filter.toLowerCase();
    return items.filter(
      (v) =>
        v.name.toLowerCase().includes(lower) ||
        v.description?.toLowerCase().includes(lower)
    );
  }, [response, filter]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
        <Loader2 className="w-3 h-3 animate-spin" />
        Loading variables...
      </div>
    );
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={isOpen ? filter : value}
        onChange={(e) => {
          setFilter(e.target.value);
          onChange(e.target.value);
          if (!isOpen) setIsOpen(true);
        }}
        onFocus={() => {
          setFilter(value);
          setIsOpen(true);
        }}
        onBlur={() => {
          setTimeout(() => setIsOpen(false), 150);
        }}
        placeholder="Type or select a variable..."
        className="w-full px-2 py-1 text-xs border border-[var(--color-border)] rounded-md bg-transparent"
      />
      {isOpen && variables.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-0.5 max-h-40 overflow-y-auto border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] shadow-lg">
          {variables.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`w-full text-left px-2 py-1.5 text-xs hover:bg-[var(--color-surface-2)] flex flex-col ${
                v.name === value ? "bg-[var(--color-surface-2)]" : ""
              }`}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(v.name);
                setFilter(v.name);
                setIsOpen(false);
              }}
            >
              <span className="font-medium">{v.name}</span>
              {v.description && (
                <span className="text-[10px] text-[var(--color-text-muted)] truncate">
                  {v.description}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
