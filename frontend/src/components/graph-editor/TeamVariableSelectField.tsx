/**
 * Dropdown field for selecting a team variable in Get/Set Team Var nodes.
 * Fetches available team variables from the API based on the active team.
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useTeamStore } from "@/stores/teamStore";
import { Loader2 } from "lucide-react";

interface TeamVariable {
  id: string;
  name: string;
  description: string | null;
  is_secret: boolean;
}

interface PaginatedResponse {
  data: TeamVariable[];
  meta: { total: number };
}

interface TeamVariableSelectFieldProps {
  value: string;
  onChange: (variableName: string) => void;
}

export function TeamVariableSelectField({ value, onChange }: TeamVariableSelectFieldProps) {
  const [filter, setFilter] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const activeTeamId = useTeamStore((s) => s.activeTeamId);

  const { data: response, isLoading } = useQuery({
    queryKey: ["team-variables", activeTeamId, "list"],
    queryFn: () => api.get<PaginatedResponse>(`/teams/${activeTeamId}/variables?per_page=100`),
    staleTime: 30_000,
    enabled: !!activeTeamId,
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

  if (!activeTeamId) {
    return (
      <div className="text-xs text-[hsl(var(--muted-foreground))]">No team selected</div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))]">
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
        placeholder="Type or select a team variable..."
        className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-transparent"
      />
      {isOpen && variables.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-0.5 max-h-40 overflow-y-auto border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg">
          {variables.map((v) => (
            <button
              key={v.id}
              type="button"
              className={`w-full text-left px-2 py-1.5 text-xs hover:bg-[hsl(var(--accent))] flex flex-col ${
                v.name === value ? "bg-[hsl(var(--accent))]" : ""
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
                <span className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">
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
