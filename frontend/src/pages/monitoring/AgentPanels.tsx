/**
 * Phase 11 — Agents + Lookup panels.
 *
 * Agents = the live roster of running SOAS instances (workers, backend,
 * frontend, etc.) keyed by stable agenttype_id. Restarts re-use the same
 * id so logs and metrics correlate across deploys.
 *
 * Lookup = deep-dive on a single agenttype_id (search → metrics history
 * over the last 24h, version changes flagged).
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Plus, Trash2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { DataTable, Th, Tr, Td } from "@/components/ui/DataTable";

interface AgentLatest {
  captured_at: string | null;
  cpu_pct: number | null;
  mem_pct: number | null;
  mem_rss_bytes: number | null;
  uptime_seconds: number | null;
  version: string | null;
  instance_id: string | null;
}

interface Agent {
  id: string | null;
  agenttype_id: string;
  role: string;
  label: string | null;
  description: string | null;
  fresh_seconds: number;
  is_enabled: boolean;
  status: "alive" | "stale" | "missing";
  latest: AgentLatest | null;
}

interface HistorySample {
  captured_at: string;
  cpu_pct: number | null;
  mem_pct: number | null;
  mem_rss_bytes: number | null;
  uptime_seconds: number | null;
  version: string | null;
  instance_id: string;
}

const STATUS_COLOR: Record<Agent["status"], string> = {
  alive: "text-[var(--color-success)]",
  stale: "text-[var(--color-warning)]",
  missing: "text-[var(--color-danger)]",
};

const STATUS_DOT_BG: Record<Agent["status"], string> = {
  alive: "bg-[var(--color-success)]",
  stale: "bg-[var(--color-warning)]",
  missing: "bg-[var(--color-danger)]",
};

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

// ============================================================
// Agents — registered roster of live instances
// ============================================================

export function RegisteredAgentsPanel({ isAdmin }: { isAdmin: boolean }) {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState({ agenttype_id: "", role: "worker", label: "" });

  const { data: agents = [], isLoading } = useQuery({
    queryKey: ["registered-agents"],
    queryFn: () => api.get<Agent[]>("/agents"),
    refetchInterval: 15000,
  });

  const create = useMutation({
    mutationFn: (body: typeof draft) => api.post<Agent>("/agents", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["registered-agents"] });
      setShowAdd(false);
      setDraft({ agenttype_id: "", role: "worker", label: "" });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/agents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["registered-agents"] }),
  });

  const counts = useMemo(() => {
    const c = { alive: 0, stale: 0, missing: 0, total: agents.length };
    for (const a of agents) c[a.status] += 1;
    return c;
  }, [agents]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Agents</h2>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            Every running SOAS instance keyed by stable <code className="font-mono">agenttype_id</code>.
            Restarts re-use the same id so logs correlate across deploys.
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowAdd((s) => !s)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
          >
            <Plus size={14} /> Register agent
          </button>
        )}
      </div>

      <div className="flex gap-2 text-xs">
        <Badge label="Alive" count={counts.alive} dotClass="bg-[var(--color-success)]" />
        <Badge label="Stale" count={counts.stale} dotClass="bg-[var(--color-warning)]" />
        <Badge label="Missing" count={counts.missing} dotClass="bg-[var(--color-danger)]" />
        <Badge label="Total" count={counts.total} dotClass="bg-[var(--color-text-muted)]" />
      </div>

      {showAdd && (
        <Card>
          <CardBody>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end">
              <Field label="agenttype_id">
                <input
                  value={draft.agenttype_id}
                  onChange={(e) => setDraft({ ...draft, agenttype_id: e.target.value.toLowerCase() })}
                  placeholder="worker_002"
                  className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
                />
              </Field>
              <Field label="Role">
                <select
                  value={draft.role}
                  onChange={(e) => setDraft({ ...draft, role: e.target.value })}
                  className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                >
                  {["worker", "backend", "frontend", "manager", "mcp", "beat", "other"].map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </Field>
              <Field label="Label (optional)">
                <input
                  value={draft.label}
                  onChange={(e) => setDraft({ ...draft, label: e.target.value })}
                  className="w-full px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
                />
              </Field>
              <div className="flex gap-2">
                <button
                  onClick={() => draft.agenttype_id && create.mutate(draft)}
                  disabled={create.isPending || !draft.agenttype_id}
                  className="px-3 py-1 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-50"
                >
                  Register
                </button>
                <button
                  onClick={() => setShowAdd(false)}
                  className="px-3 py-1 text-sm rounded border border-[var(--color-border)]"
                >
                  Cancel
                </button>
              </div>
            </div>
            {create.error && (
              <p className="text-xs text-[var(--color-danger)] mt-2 font-mono">
                {(create.error as Error).message}
              </p>
            )}
          </CardBody>
        </Card>
      )}

      <Card>
        <CardBody>
          {isLoading && <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>}
          {!isLoading && agents.length === 0 && (
            <div className="text-sm text-[var(--color-text-muted)] py-8 text-center">
              No agents reporting yet. Workers register themselves on first heartbeat.
            </div>
          )}
          {!isLoading && agents.length > 0 && (
            <DataTable>
              <thead>
                <tr>
                  <Th>Status</Th>
                  <Th>Agent ID</Th>
                  <Th>Role</Th>
                  <Th>Label</Th>
                  <Th>Version</Th>
                  <Th align="right">CPU %</Th>
                  <Th align="right">Mem %</Th>
                  <Th align="right">RSS</Th>
                  <Th align="right">Uptime</Th>
                  <Th>Last seen</Th>
                  {isAdmin && <Th align="right">Actions</Th>}
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <Tr key={a.agenttype_id}>
                    <Td>
                      <span className="inline-flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${STATUS_DOT_BG[a.status]}`} />
                        <span className={`text-[11px] uppercase font-semibold tracking-wide ${STATUS_COLOR[a.status]}`}>
                          {a.status}
                        </span>
                      </span>
                    </Td>
                    <Td className="font-mono text-xs">{a.agenttype_id}</Td>
                    <Td>{a.role}</Td>
                    <Td>{a.label ?? "—"}</Td>
                    <Td className="font-mono text-xs">{a.latest?.version ?? "—"}</Td>
                    <Td align="right" className="font-mono">{a.latest?.cpu_pct?.toFixed(1) ?? "—"}</Td>
                    <Td align="right" className="font-mono">{a.latest?.mem_pct?.toFixed(1) ?? "—"}</Td>
                    <Td align="right" className="font-mono">{fmtBytes(a.latest?.mem_rss_bytes ?? null)}</Td>
                    <Td align="right" className="font-mono">{fmtUptime(a.latest?.uptime_seconds ?? null)}</Td>
                    <Td className="font-mono text-[11px] text-[var(--color-text-muted)]">
                      {a.latest?.captured_at ? new Date(a.latest.captured_at).toLocaleTimeString() : "never"}
                    </Td>
                    {isAdmin && (
                      <Td align="right">
                        {a.id && (
                          <button
                            onClick={() => confirm(`Remove ${a.agenttype_id}?`) && remove.mutate(a.id!)}
                            className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                            title="Remove from registry"
                          >
                            <Trash2 size={12} />
                          </button>
                        )}
                      </Td>
                    )}
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

// ============================================================
// Lookup — deep-dive on one agenttype_id
// ============================================================

export function LookupPanel() {
  const [agentId, setAgentId] = useState<string>("");
  const [committed, setCommitted] = useState<string>("");
  const [hours, setHours] = useState<number>(24);

  const { data: agents = [] } = useQuery({
    queryKey: ["registered-agents-for-lookup"],
    queryFn: () => api.get<Agent[]>("/agents"),
  });

  const { data: history = [], isLoading } = useQuery({
    queryKey: ["agent-history", committed, hours],
    queryFn: () =>
      api.get<HistorySample[]>(`/agents/${committed}/history?hours=${hours}`),
    enabled: !!committed,
  });

  const versionChanges = useMemo(() => {
    const out: { ts: string; from: string | null; to: string | null }[] = [];
    let prev: string | null | undefined;
    for (const h of history) {
      if (prev !== undefined && prev !== h.version) {
        out.push({ ts: h.captured_at, from: prev ?? null, to: h.version });
      }
      prev = h.version;
    }
    return out;
  }, [history]);

  const filtered = useMemo(() => {
    const q = agentId.toLowerCase().trim();
    if (!q) return agents.slice(0, 10);
    return agents.filter(
      (a) =>
        a.agenttype_id.toLowerCase().includes(q) ||
        a.role.toLowerCase().includes(q) ||
        (a.label ?? "").toLowerCase().includes(q),
    );
  }, [agents, agentId]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Lookup</h2>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          Deep dive on a single agent. Search by id, role, or label — works for currently-running
          and historical instances.
        </p>
      </div>

      <Card>
        <CardBody>
          <div className="flex gap-2 items-center">
            <div className="relative flex-1">
              <Search
                size={14}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
              />
              <input
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && agentId && setCommitted(agentId)}
                placeholder="Type an agenttype_id, role, or label…"
                className="w-full pl-7 pr-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
              />
            </div>
            <select
              value={hours}
              onChange={(e) => setHours(parseInt(e.target.value))}
              className="px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            >
              <option value={1}>1h</option>
              <option value={6}>6h</option>
              <option value={24}>24h</option>
              <option value={72}>3d</option>
              <option value={168}>7d</option>
            </select>
          </div>

          {!committed && (
            <div className="mt-3 space-y-1">
              {filtered.length === 0 && (
                <div className="text-sm text-[var(--color-text-muted)] py-4 text-center">
                  No agents match your search.
                </div>
              )}
              {filtered.map((a) => (
                <button
                  key={a.agenttype_id}
                  onClick={() => setCommitted(a.agenttype_id)}
                  className="w-full text-left px-2 py-1.5 rounded text-sm flex items-center gap-3 hover:bg-[var(--color-surface-2)]"
                >
                  <span className={`w-2 h-2 rounded-full ${STATUS_DOT_BG[a.status]}`} />
                  <span className="font-mono text-xs">{a.agenttype_id}</span>
                  <span className="text-[var(--color-text-muted)]">{a.role}</span>
                  {a.label && <span className="text-[var(--color-text-muted)]">· {a.label}</span>}
                </button>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {committed && (
        <>
          <div className="flex items-center justify-between">
            <div className="text-sm text-[var(--color-text-muted)]">
              Showing <span className="font-mono text-[var(--color-text)]">{committed}</span> · last {hours}h
            </div>
            <button
              onClick={() => {
                setCommitted("");
                setAgentId("");
              }}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline"
            >
              Change agent
            </button>
          </div>

          {isLoading && (
            <Card>
              <CardBody>
                <div className="text-sm text-[var(--color-text-muted)] py-8 text-center">Loading…</div>
              </CardBody>
            </Card>
          )}

          {!isLoading && history.length === 0 && (
            <Card>
              <CardBody>
                <div className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                  No samples for this agent in the selected window.
                </div>
              </CardBody>
            </Card>
          )}

          {!isLoading && history.length > 0 && (
            <>
              <Card>
                <CardBody>
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
                    CPU & Memory
                  </div>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={history} margin={{ left: 16, right: 16, top: 8, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis
                        dataKey="captured_at"
                        stroke="var(--color-text-muted)"
                        fontSize={11}
                        tickFormatter={(v) => new Date(v).toLocaleTimeString()}
                      />
                      <YAxis stroke="var(--color-text-muted)" fontSize={11} />
                      <Tooltip
                        contentStyle={{
                          background: "var(--color-surface)",
                          border: "1px solid var(--color-border)",
                          fontSize: 12,
                        }}
                      />
                      <Line type="monotone" dataKey="cpu_pct" name="CPU %" stroke="#0b63ce" dot={false} />
                      <Line type="monotone" dataKey="mem_pct" name="Mem %" stroke="#00c389" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardBody>
              </Card>

              <Card>
                <CardBody>
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
                    Version timeline
                  </div>
                  {versionChanges.length === 0 ? (
                    <div className="text-xs text-[var(--color-text-muted)]">
                      No version changes in this window. Current:{" "}
                      <span className="font-mono">{history[history.length - 1]?.version ?? "—"}</span>
                    </div>
                  ) : (
                    <ul className="space-y-1 text-xs font-mono">
                      {versionChanges.map((v, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <span className="text-[var(--color-text-muted)]">
                            {new Date(v.ts).toLocaleString()}
                          </span>
                          <span>
                            <span className="text-[var(--color-text-muted)]">{v.from ?? "?"}</span>
                            {" → "}
                            <span className="text-[var(--color-primary)]">{v.to ?? "?"}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardBody>
              </Card>

              <LogsPanel agenttypeId={committed} />

              <Card>
                <CardBody>
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
                    Raw samples ({history.length})
                  </div>
                  <div className="max-h-64 overflow-auto">
                    <DataTable>
                      <thead>
                        <tr>
                          <Th>Time</Th>
                          <Th>Instance</Th>
                          <Th>Version</Th>
                          <Th align="right">CPU %</Th>
                          <Th align="right">Mem %</Th>
                          <Th align="right">RSS</Th>
                          <Th align="right">Uptime</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {history.slice().reverse().slice(0, 200).map((s, i) => (
                          <Tr key={i}>
                            <Td className="font-mono text-[11px]">
                              {new Date(s.captured_at).toLocaleString()}
                            </Td>
                            <Td className="font-mono text-[11px]">{s.instance_id}</Td>
                            <Td className="font-mono text-[11px]">{s.version ?? "—"}</Td>
                            <Td align="right" className="font-mono">{s.cpu_pct?.toFixed(1) ?? "—"}</Td>
                            <Td align="right" className="font-mono">{s.mem_pct?.toFixed(1) ?? "—"}</Td>
                            <Td align="right" className="font-mono">{fmtBytes(s.mem_rss_bytes)}</Td>
                            <Td align="right" className="font-mono">{fmtUptime(s.uptime_seconds)}</Td>
                          </Tr>
                        ))}
                      </tbody>
                    </DataTable>
                  </div>
                </CardBody>
              </Card>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ============================================================
// Local helpers
// ============================================================

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

function Badge({ label, count, dotClass }: { label: string; count: number; dotClass: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--color-surface-2)]">
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
      <span className="text-[var(--color-text-muted)]">{label}:</span>
      <span className="font-mono font-semibold">{count}</span>
    </span>
  );
}

// ============================================================
// Logs — viewer for one agent's recent logs
// ============================================================

interface LogRow {
  id: string;
  level: string;
  message: string;
  context: Record<string, unknown>;
  version: string | null;
  occurred_at: string | null;
  created_at: string;
}

const LEVEL_COLOR: Record<string, string> = {
  debug: "text-[var(--color-text-muted)]",
  info: "text-[var(--color-text)]",
  warn: "text-[var(--color-warning)]",
  error: "text-[var(--color-danger)]",
  fatal: "text-[var(--color-danger)]",
};

function LogsPanel({ agenttypeId }: { agenttypeId: string }) {
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<string>("");
  const [limit, setLimit] = useState(200);

  const { data: logs = [], isLoading, refetch } = useQuery({
    queryKey: ["agent-logs", agenttypeId, level, search, limit],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (level) params.set("level", level);
      if (search.trim()) params.set("search", search.trim());
      return api.get<LogRow[]>(`/agents/${agenttypeId}/logs?${params.toString()}`);
    },
    refetchInterval: 15000,
  });

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between mb-2 gap-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            Logs ({logs.length}{logs.length === limit ? "+" : ""})
          </div>
          <div className="flex gap-2">
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="px-2 py-1 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            >
              <option value="">All levels</option>
              <option value="debug">debug</option>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="error">error</option>
              <option value="fatal">fatal</option>
            </select>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && refetch()}
              placeholder="Search messages…"
              className="w-40 px-2 py-1 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
            />
            <select
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              className="px-2 py-1 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
            >
              <option value={50}>50</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
              <option value={2000}>2000</option>
            </select>
          </div>
        </div>
        {isLoading && <div className="text-xs text-[var(--color-text-muted)]">Loading…</div>}
        {!isLoading && logs.length === 0 && (
          <div className="text-xs text-[var(--color-text-muted)] py-6 text-center">
            No logs for this agent yet. Agents post via POST /api/v1/agents/{"{id}"}/logs.
          </div>
        )}
        {logs.length > 0 && (
          <div className="max-h-96 overflow-auto font-mono text-[11.5px] border border-[var(--color-border)] rounded bg-[var(--color-surface-2)]">
            {logs.map((r) => (
              <div
                key={r.id}
                className="px-2 py-1 border-b border-[var(--color-border)] last:border-b-0"
              >
                <div className="flex items-baseline gap-2">
                  <span className="text-[var(--color-text-muted)] shrink-0">
                    {new Date(r.created_at).toLocaleTimeString()}
                  </span>
                  <span
                    className={`uppercase shrink-0 text-[10px] font-semibold tracking-wide ${
                      LEVEL_COLOR[r.level] ?? "text-[var(--color-text)]"
                    }`}
                  >
                    {r.level}
                  </span>
                  {r.version && (
                    <span className="text-[10px] text-[var(--color-text-muted)] shrink-0">
                      v{r.version}
                    </span>
                  )}
                  <span className={`flex-1 whitespace-pre-wrap break-words ${LEVEL_COLOR[r.level] ?? ""}`}>
                    {r.message}
                  </span>
                </div>
                {Object.keys(r.context).length > 0 && (
                  <pre className="text-[10px] text-[var(--color-text-muted)] pl-16 mt-0.5 whitespace-pre-wrap">
                    {JSON.stringify(r.context)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
