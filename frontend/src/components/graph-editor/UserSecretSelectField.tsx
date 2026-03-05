/**
 * Dropdown field for selecting a user secret in the Get User Secret node.
 * Fetches the current user's secrets from the API with type-ahead filtering.
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

interface UserSecret {
  id: string;
  name: string;
  description: string | null;
}

interface PaginatedResponse {
  data: UserSecret[];
  meta: { total: number };
}

interface UserSecretSelectFieldProps {
  value: string;
  onChange: (secretName: string) => void;
}

export function UserSecretSelectField({ value, onChange }: UserSecretSelectFieldProps) {
  const [filter, setFilter] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const { data: response, isLoading } = useQuery({
    queryKey: ["user-secrets", "list"],
    queryFn: () => api.get<PaginatedResponse>("/user-secrets?per_page=100"),
    staleTime: 30_000,
  });

  const secrets = useMemo(() => {
    const items = response?.data || [];
    if (!filter) return items;
    const lower = filter.toLowerCase();
    return items.filter(
      (s) =>
        s.name.toLowerCase().includes(lower) ||
        s.description?.toLowerCase().includes(lower)
    );
  }, [response, filter]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))]">
        <Loader2 className="w-3 h-3 animate-spin" />
        Loading secrets...
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
        placeholder="Type or select a secret..."
        className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-transparent"
      />
      {isOpen && secrets.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-0.5 max-h-40 overflow-y-auto border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg">
          {secrets.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`w-full text-left px-2 py-1.5 text-xs hover:bg-[hsl(var(--accent))] flex flex-col ${
                s.name === value ? "bg-[hsl(var(--accent))]" : ""
              }`}
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(s.name);
                setFilter(s.name);
                setIsOpen(false);
              }}
            >
              <span className="font-medium">{s.name}</span>
              {s.description && (
                <span className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">
                  {s.description}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
