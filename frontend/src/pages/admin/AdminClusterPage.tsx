import { useQuery } from "@tanstack/react-query";
import { Server } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { DataTable, Th, Td, Tr } from "@/components/ui/DataTable";

interface Sample {
  instance_id: string;
  role: string | null;
  cpu_pct: number | null;
  mem_pct: number | null;
  mem_rss_bytes: number | null;
  net_in_bytes: number | null;
  net_out_bytes: number | null;
  uptime_seconds: number | null;
  version: string | null;
  captured_at: string;
}

interface NetIO {
  minute_utc: string;
  source: string;
  bytes_in: number;
  bytes_out: number;
  request_count: number;
  error_count: number;
}

function fmtBytes(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function fmtUptime(s: number | null): string {
  if (s === null || s <= 0) return "—";
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/**
 * Cluster panel — also exported as a panel for embedding inside the Monitoring page.
 * The standalone page is kept as a thin wrapper so existing /admin/cluster URLs still resolve.
 */
export function ClusterPanel() {
  return <AdminClusterPageBody />;
}

export function AdminClusterPage() {
  return <AdminClusterPageBody />;
}

function AdminClusterPageBody() {
  const { data: samples = [] } = useQuery({
    queryKey: ["cluster-samples"],
    queryFn: () => api.get<Sample[]>("/observability/cluster?since_minutes=15"),
    refetchInterval: 15000,
  });
  const { data: netio = [] } = useQuery({
    queryKey: ["network-io"],
    queryFn: () => api.get<NetIO[]>("/observability/network-io?since_hours=24"),
  });

  // Latest sample per instance
  const latestByInstance = new Map<string, Sample>();
  for (const s of samples) {
    const cur = latestByInstance.get(s.instance_id);
    if (!cur || s.captured_at > cur.captured_at) latestByInstance.set(s.instance_id, s);
  }

  // Aggregate network IO by source (last 24h)
  const bySource = new Map<string, { in: number; out: number; reqs: number; errs: number }>();
  for (const r of netio) {
    const cur = bySource.get(r.source) ?? { in: 0, out: 0, reqs: 0, errs: 0 };
    cur.in += r.bytes_in;
    cur.out += r.bytes_out;
    cur.reqs += r.request_count;
    cur.errs += r.error_count;
    bySource.set(r.source, cur);
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Server size={18} /> Cluster
        </h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          Per-instance CPU / memory / network metrics, refreshed every 15s.
        </p>
      </div>

      <Card>
        <CardBody>
          <DataTable>
            <thead>
              <tr>
                <Th>Instance</Th>
                <Th>Role</Th>
                <Th align="right">CPU %</Th>
                <Th align="right">Mem %</Th>
                <Th align="right">RSS</Th>
                <Th align="right">Net in</Th>
                <Th align="right">Net out</Th>
                <Th align="right">Uptime</Th>
                <Th>Version</Th>
              </tr>
            </thead>
            <tbody>
              {Array.from(latestByInstance.values()).map((s) => (
                <Tr key={s.instance_id}>
                  <Td className="font-mono text-xs">{s.instance_id}</Td>
                  <Td>{s.role ?? "—"}</Td>
                  <Td align="right" className="font-mono">{s.cpu_pct?.toFixed(1) ?? "—"}</Td>
                  <Td align="right" className="font-mono">{s.mem_pct?.toFixed(1) ?? "—"}</Td>
                  <Td align="right" className="font-mono">{fmtBytes(s.mem_rss_bytes)}</Td>
                  <Td align="right" className="font-mono">{fmtBytes(s.net_in_bytes)}</Td>
                  <Td align="right" className="font-mono">{fmtBytes(s.net_out_bytes)}</Td>
                  <Td align="right" className="font-mono">{fmtUptime(s.uptime_seconds)}</Td>
                  <Td className="font-mono text-xs">{s.version ?? "—"}</Td>
                </Tr>
              ))}
              {latestByInstance.size === 0 && (
                <tr>
                  <Td className="text-center text-[var(--color-text-muted)]">No instances reporting metrics. Worker heartbeat task may not be writing samples yet.</Td>
                </tr>
              )}
            </tbody>
          </DataTable>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
            Network I/O by source — last 24h
          </div>
          <DataTable>
            <thead>
              <tr>
                <Th>Source</Th>
                <Th align="right">Bytes in</Th>
                <Th align="right">Bytes out</Th>
                <Th align="right">Requests</Th>
                <Th align="right">Errors</Th>
              </tr>
            </thead>
            <tbody>
              {Array.from(bySource.entries()).map(([source, sums]) => (
                <Tr key={source}>
                  <Td className="font-mono text-xs">{source}</Td>
                  <Td align="right" className="font-mono">{fmtBytes(sums.in)}</Td>
                  <Td align="right" className="font-mono">{fmtBytes(sums.out)}</Td>
                  <Td align="right" className="font-mono">{sums.reqs.toLocaleString()}</Td>
                  <Td align="right" className="font-mono">{sums.errs.toLocaleString()}</Td>
                </Tr>
              ))}
              {bySource.size === 0 && (
                <tr>
                  <Td className="text-center text-[var(--color-text-muted)]">No network I/O recorded.</Td>
                </tr>
              )}
            </tbody>
          </DataTable>
        </CardBody>
      </Card>
    </div>
  );
}
