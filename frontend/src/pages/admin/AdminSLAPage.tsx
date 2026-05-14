import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { DataTable, Th, Td, Tr } from "@/components/ui/DataTable";

interface SLADef {
  id: string;
  key: string;
  label: string;
  description: string | null;
  target_seconds: number;
  dimension: string;
  end_column: string;
  is_enabled: boolean;
}

interface SLASnap {
  sla_key: string;
  dim_value: string;
  captured_for: string;
  total_count: number;
  compliant_count: number;
  compliance_pct: number;
  p50_seconds: number | null;
  p95_seconds: number | null;
}

export function AdminSLAPage() {
  const qc = useQueryClient();
  const { data: defs = [] } = useQuery({ queryKey: ["slas"], queryFn: () => api.get<SLADef[]>("/slas") });
  const { data: snaps = [] } = useQuery({
    queryKey: ["sla-snapshots"],
    queryFn: () => api.get<SLASnap[]>("/slas/snapshots?days=30"),
  });
  const [recomputing, setRecomputing] = useState(false);
  const recompute = useMutation({
    mutationFn: () => api.post<Record<string, number>>("/slas/recompute"),
    onMutate: () => setRecomputing(true),
    onSettled: () => {
      setRecomputing(false);
      qc.invalidateQueries({ queryKey: ["sla-snapshots"] });
    },
  });

  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<SLADef> }) =>
      api.patch<SLADef>(`/slas/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["slas"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">SLA Definitions</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            MTTI / MTTA / MTTR targets, with daily snapshots written by Celery beat (02:15 UTC).
          </p>
        </div>
        <button
          onClick={() => recompute.mutate()}
          disabled={recomputing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
        >
          <RefreshCw size={14} className={recomputing ? "animate-spin" : ""} />
          Recompute now
        </button>
      </div>

      <Card>
        <CardBody>
          <DataTable>
            <thead>
              <tr>
                <Th>Key</Th>
                <Th>Label</Th>
                <Th>End column</Th>
                <Th>Target (s)</Th>
                <Th>Dimension</Th>
                <Th>Enabled</Th>
              </tr>
            </thead>
            <tbody>
              {defs.map((d) => (
                <Tr key={d.id}>
                  <Td className="font-mono text-xs">{d.key}</Td>
                  <Td>{d.label}</Td>
                  <Td className="font-mono text-xs">{d.end_column}</Td>
                  <Td>
                    <input
                      type="number"
                      defaultValue={d.target_seconds}
                      onBlur={(e) => {
                        const v = parseInt(e.target.value);
                        if (!isNaN(v) && v !== d.target_seconds) update.mutate({ id: d.id, body: { target_seconds: v } });
                      }}
                      className="w-24 px-1.5 py-0.5 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                    />
                  </Td>
                  <Td className="font-mono text-xs">{d.dimension}</Td>
                  <Td>
                    <input
                      type="checkbox"
                      checked={d.is_enabled}
                      onChange={(e) => update.mutate({ id: d.id, body: { is_enabled: e.target.checked } })}
                    />
                  </Td>
                </Tr>
              ))}
            </tbody>
          </DataTable>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
            Recent compliance snapshots
          </div>
          {snaps.length === 0 ? (
            <div className="py-6 text-sm text-[var(--color-text-muted)] text-center">
              <Activity size={20} className="mx-auto mb-1" />
              No snapshots yet — try "Recompute now".
            </div>
          ) : (
            <DataTable>
              <thead>
                <tr>
                  <Th>Day</Th>
                  <Th>SLA</Th>
                  <Th>Dimension</Th>
                  <Th align="right">Total</Th>
                  <Th align="right">Compliant</Th>
                  <Th align="right">%</Th>
                  <Th align="right">p50 (s)</Th>
                  <Th align="right">p95 (s)</Th>
                </tr>
              </thead>
              <tbody>
                {snaps.map((s, i) => (
                  <Tr key={i}>
                    <Td className="font-mono text-xs">{s.captured_for}</Td>
                    <Td className="font-mono text-xs">{s.sla_key}</Td>
                    <Td className="font-mono text-xs">{s.dim_value}</Td>
                    <Td align="right">{s.total_count}</Td>
                    <Td align="right">{s.compliant_count}</Td>
                    <Td align="right" className="font-mono">{s.compliance_pct.toFixed(1)}%</Td>
                    <Td align="right" className="font-mono">{s.p50_seconds?.toFixed(0) ?? "—"}</Td>
                    <Td align="right" className="font-mono">{s.p95_seconds?.toFixed(0) ?? "—"}</Td>
                  </Tr>
                ))}
              </tbody>
            </DataTable>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
