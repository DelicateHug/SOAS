import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ShieldCheck, ShieldOff } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

interface Optin {
  user_id: string;
  opted_in_at: string;
  granted_by: string | null;
  user_display: string | null;
}

interface DangerSummary {
  counts: Record<string, number>;
}

export function AdminDangerZonePage() {
  const qc = useQueryClient();
  const { data: optins = [] } = useQuery({ queryKey: ["optins"], queryFn: () => api.get<Optin[]>("/admin/optins") });
  const { data: summary } = useQuery({ queryKey: ["danger-summary"], queryFn: () => api.get<DangerSummary>("/admin/danger-zone/summary") });

  const grant = useMutation({
    mutationFn: (userId: string) => api.post(`/admin/optins/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["optins"] }),
  });
  const revoke = useMutation({
    mutationFn: (userId: string) => api.delete(`/admin/optins/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["optins"] }),
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <AlertTriangle size={18} className="text-[var(--color-danger)]" />
          Danger Zone
        </h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          Sensitive admin actions: user opt-in roster, system counters, forced syncs.
        </p>
      </div>

      <Card>
        <CardBody>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
            System inventory
          </div>
          {summary ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(summary.counts).map(([k, v]) => (
                <div key={k} className="text-center p-3 bg-[var(--color-surface-2)] rounded">
                  <div className="text-2xl font-mono font-bold text-[var(--color-text)]">{v.toLocaleString()}</div>
                  <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-muted)] mt-0.5">{k}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
            Automation opt-ins
          </div>
          <p className="text-xs text-[var(--color-text-muted)] mb-3">
            Users below have explicitly opted in to run automations and create scheduled jobs.
            This is an extra gate on top of RBAC permissions.
          </p>
          <UserPicker onPick={(userId) => grant.mutate(userId)} />
          <div className="mt-3 space-y-1">
            {optins.length === 0 && (
              <div className="text-xs text-[var(--color-text-muted)] py-3 text-center">No users have opted in yet.</div>
            )}
            {optins.map((o) => (
              <div key={o.user_id} className="flex items-center justify-between px-2 py-1.5 bg-[var(--color-surface-2)] rounded text-sm">
                <div className="flex items-center gap-2">
                  <ShieldCheck size={14} className="text-[var(--color-success)]" />
                  <span>{o.user_display ?? o.user_id}</span>
                  <span className="text-[10px] text-[var(--color-text-muted)] font-mono">
                    opted in {new Date(o.opted_in_at).toLocaleDateString()}
                  </span>
                </div>
                <button
                  onClick={() => confirm(`Revoke opt-in for ${o.user_display}?`) && revoke.mutate(o.user_id)}
                  className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
                >
                  <ShieldOff size={11} /> Revoke
                </button>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function UserPicker({ onPick }: { onPick: (id: string) => void }) {
  // Minimal: read /users (admin role required) and let admin pick.
  const { data: users = [] } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<{ id: string; display_name: string; username: string }[]>("/users"),
  });
  return (
    <select
      onChange={(e) => {
        if (e.target.value) {
          onPick(e.target.value);
          e.target.value = "";
        }
      }}
      defaultValue=""
      className="w-full max-w-md px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
    >
      <option value="">Grant opt-in to user…</option>
      {users.map((u) => (
        <option key={u.id} value={u.id}>
          {u.display_name} ({u.username})
        </option>
      ))}
    </select>
  );
}
