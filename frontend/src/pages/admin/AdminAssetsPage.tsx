import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";
import { DataTable, Th, Td, Tr } from "@/components/ui/DataTable";

interface Asset {
  id: string;
  asset_type: string;
  identifier: string;
  label: string | null;
  tags: string[];
  is_active: boolean;
}

const TYPES = ["user", "host", "ip", "account"] as const;

export function AdminAssetsPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detectResult, setDetectResult] = useState<unknown>(null);
  const [showNew, setShowNew] = useState(false);
  const [newType, setNewType] = useState<typeof TYPES[number]>("host");
  const [newIdent, setNewIdent] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [tf, setTf] = useState("last_30d");

  const { data: assets = [] } = useQuery({
    queryKey: ["assets"],
    queryFn: () => api.get<Asset[]>("/assets"),
  });
  const create = useMutation({
    mutationFn: (b: { asset_type: string; identifier: string; label?: string }) =>
      api.post<Asset>("/assets", b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assets"] });
      setShowNew(false);
      setNewIdent("");
      setNewLabel("");
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/assets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });

  async function detect(id: string) {
    setActiveId(id);
    setDetectResult(null);
    const r = await api.get(`/assets/${id}/detect?timeframe=${tf}`);
    setDetectResult(r);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Assets</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            Define known users / hosts / IPs / accounts. Click "Detect" to find recent incidents that reference them.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={tf} onChange={(e) => setTf(e.target.value)} className="px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]">
            <option value="last_24h">Last 24h</option>
            <option value="last_7d">Last 7d</option>
            <option value="last_30d">Last 30d</option>
            <option value="last_90d">Last 90d</option>
          </select>
          <button
            onClick={() => setShowNew(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
          >
            <Plus size={14} /> New asset
          </button>
        </div>
      </div>

      {showNew && (
        <Card>
          <CardBody>
            <div className="flex items-end gap-2">
              <select value={newType} onChange={(e) => setNewType(e.target.value as typeof TYPES[number])} className="px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]">
                {TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
              <input value={newIdent} onChange={(e) => setNewIdent(e.target.value)} placeholder="identifier (hostname / username / IP)" className="flex-1 px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono" />
              <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="label (optional)" className="flex-1 px-2 py-1 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]" />
              <button
                onClick={() => newIdent.trim() && create.mutate({ asset_type: newType, identifier: newIdent.trim(), label: newLabel.trim() || undefined })}
                className="px-3 py-1 rounded bg-[var(--color-primary)] text-white text-sm"
              >
                Create
              </button>
              <button onClick={() => setShowNew(false)} className="px-3 py-1 rounded border border-[var(--color-border)] text-sm">
                Cancel
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardBody>
          <DataTable>
            <thead>
              <tr>
                <Th>Type</Th>
                <Th>Identifier</Th>
                <Th>Label</Th>
                <Th>Active</Th>
                <Th align="right">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => (
                <Tr key={a.id}>
                  <Td className="font-mono text-xs">{a.asset_type}</Td>
                  <Td className="font-mono">{a.identifier}</Td>
                  <Td>{a.label}</Td>
                  <Td>{a.is_active ? "yes" : "no"}</Td>
                  <Td align="right">
                    <button onClick={() => detect(a.id)} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] mr-1">
                      <Search size={11} /> Detect
                    </button>
                    <button
                      onClick={() => confirm(`Delete ${a.identifier}?`) && remove.mutate(a.id)}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                    >
                      <Trash2 size={12} />
                    </button>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </DataTable>
        </CardBody>
      </Card>

      {activeId && (
        <Card>
          <CardBody>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              Detection result
            </div>
            <pre className="text-xs font-mono bg-[var(--color-surface-2)] p-3 rounded overflow-auto max-h-96">
              {detectResult ? JSON.stringify(detectResult, null, 2) : "Running…"}
            </pre>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
