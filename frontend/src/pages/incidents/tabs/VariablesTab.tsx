import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { JsonViewer } from "@/components/ui/JsonViewer";
import type { Incident } from "@/types/api";

interface Props {
  incidentId: string;
}

function VariableRow({ name, value, type }: { name: string; value: string; type: string }) {
  return (
    <tr>
      <td className="px-4 py-2 font-mono text-xs text-blue-400">{name}</td>
      <td className="px-4 py-2 font-mono text-xs max-w-md truncate">{value}</td>
      <td className="px-4 py-2 text-xs text-[var(--color-text-muted)]">{type}</td>
    </tr>
  );
}

function VariableTableHeader() {
  return (
    <thead>
      <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
        <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Variable
        </th>
        <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Value
        </th>
        <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          Type
        </th>
      </tr>
    </thead>
  );
}

export function VariablesTab({ incidentId }: Props) {
  const { data: incident } = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => api.get<Incident>(`/incidents/${incidentId}`),
  });

  const metadata = incident?.metadata || {};
  const entries = Object.entries(metadata);

  const systemVars: { name: string; value: string; type: string }[] = [];
  if (incident) {
    systemVars.push({ name: "incident_id", value: incident.id, type: "string" });
    systemVars.push({
      name: "case_id",
      value: incident.case_id ?? "null",
      type: incident.case_id ? "string" : "null",
    });
    systemVars.push({ name: "created_at", value: incident.created_at, type: "string" });
    systemVars.push({
      name: "closed_at",
      value: incident.closed_at ?? "null",
      type: incident.closed_at ? "string" : "null",
    });
  }

  return (
    <div className="space-y-6">
      {/* System variables */}
      <div>
        <SectionHeader title="System Variables" />
        <div className="rounded-lg border border-[var(--color-border)] overflow-hidden">
          <table className="w-full text-sm">
            <VariableTableHeader />
            <tbody className="divide-y divide-[var(--color-border)]">
              {systemVars.map((v) => (
                <VariableRow key={v.name} {...v} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Incident metadata variables */}
      <SectionHeader title="Incident Variables" />

      {entries.length === 0 ? (
        <div className="py-8 text-center text-[var(--color-text-muted)]">
          No variables set for this incident
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg border border-[var(--color-border)] overflow-hidden">
            <table className="w-full text-sm">
              <VariableTableHeader />
              <tbody className="divide-y divide-[var(--color-border)]">
                {entries.map(([key, value]) => (
                  <VariableRow
                    key={key}
                    name={key}
                    value={
                      typeof value === "object"
                        ? JSON.stringify(value).slice(0, 100) +
                          (JSON.stringify(value).length > 100 ? "..." : "")
                        : String(value)
                    }
                    type={value === null ? "null" : Array.isArray(value) ? "array" : typeof value}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <SectionHeader title="Full Data" />
            <JsonViewer data={metadata} />
          </div>
        </div>
      )}
    </div>
  );
}
