/**
 * Dropdown field for selecting a target automation in the Run Automation node.
 * Fetches automations the user has "can_read" and "can_add" permissions for.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

export interface AutomationInputDef {
  name: string;
  type: string; // "STRING" | "INTEGER" | "FLOAT" | "BOOLEAN" | "LIST" | "DICT" | "ANY"
  required: boolean;
  default_value: unknown;
  description: string;
}

interface AddableAutomation {
  id: string;
  name: string;
  description: string | null;
  status: string;
  parameters: AutomationInputDef[];
}

interface AutomationSelectFieldProps {
  value: string;
  currentAutomationId?: string;
  onChange: (automationId: string, automationName: string, parameters: AutomationInputDef[]) => void;
}

export function AutomationSelectField({
  value,
  currentAutomationId,
  onChange,
}: AutomationSelectFieldProps) {
  const queryParams = currentAutomationId
    ? `?exclude_id=${currentAutomationId}`
    : "";

  const { data: automations, isLoading } = useQuery({
    queryKey: ["automations", "addable", currentAutomationId],
    queryFn: () =>
      api.get<AddableAutomation[]>(`/automations/addable${queryParams}`),
    staleTime: 30_000,
  });

  const items = Array.isArray(automations) ? automations : [];

  if (isLoading) {
    return (
      <div className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))]">
        <Loader2 className="w-3 h-3 animate-spin" />
        Loading automations...
      </div>
    );
  }

  return (
    <div>
      <select
        value={value}
        onChange={(e) => {
          const selected = items.find((a) => a.id === e.target.value);
          onChange(
            e.target.value,
            selected?.name || "",
            selected?.parameters || []
          );
        }}
        className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-transparent"
      >
        <option value="">-- Select Automation --</option>
        {items.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
      </select>
      {!isLoading && items.length === 0 && (
        <p className="text-[10px] text-[hsl(var(--muted-foreground))] mt-1">
          No automations available. Automations must be set to
          &ldquo;active&rdquo; status and have read + add permissions.
        </p>
      )}
    </div>
  );
}
