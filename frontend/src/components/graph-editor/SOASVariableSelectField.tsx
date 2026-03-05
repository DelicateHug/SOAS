/**
 * Dropdown field for selecting a SOAS variable in Get/Set SOAS Var nodes.
 * Fetches available SOAS variables from the API with type-ahead filtering.
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

interface SOASVariable {
  id: string;
  name: string;
  description: string | null;
  is_secret: boolean;
  source?: "soas_var" | "shared_secret";
  owner_username?: string | null;
}

interface PaginatedResponse {
  data: SOASVariable[];
  meta: { total: number };
}

interface SOASVariableSelectFieldProps {
  value: string;
  onChange: (variableName: string) => void;
}

export function SOASVariableSelectField({ value, onChange }: SOASVariableSelectFieldProps) {
  const [filter, setFilter] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const { data: response, isLoading } = useQuery({
    queryKey: ["soas-variables", "list"],
    queryFn: () => api.get<PaginatedResponse>("/soas-variables?per_page=100&include_shared=true"),
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
          // Delay to allow click on dropdown items
          setTimeout(() => setIsOpen(false), 150);
        }}
        placeholder="Type or select a variable..."
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
              <span className="font-medium flex items-center gap-1">
                {v.name}
                {v.source === "shared_secret" && (
                  <span className="inline-flex items-center px-1 py-0.5 rounded text-[9px] font-medium bg-blue-500/20 text-blue-400 leading-none">
                    Shared
                  </span>
                )}
              </span>
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
