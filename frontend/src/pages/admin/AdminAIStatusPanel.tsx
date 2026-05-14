/**
 * AI auth status panel.
 *
 * Reports which AI auth path is live: Claude CLI + OAuth (subscription),
 * Claude CLI + API key, or none. Gives the analyst the exact command to fix
 * the "none" case.
 */
import { useQuery } from "@tanstack/react-query";
import { Sparkles, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

interface AIStatus {
  active: "cli_oauth" | "cli_api_key" | "sdk_api_key" | "none";
  message: string;
  cli: {
    present: boolean;
    version: string | null;
    oauth_logged_in: boolean;
    auth_error: string | null;
  };
  api_key: { set: boolean };
  hints: { subscription: string; api_key_env_var: string };
}

const statusColor: Record<AIStatus["active"], string> = {
  cli_oauth: "text-emerald-500",
  cli_api_key: "text-emerald-500",
  sdk_api_key: "text-amber-500",
  none: "text-[var(--color-danger)]",
};

const statusLabel: Record<AIStatus["active"], string> = {
  cli_oauth: "Active · CLI + OAuth (subscription)",
  cli_api_key: "Active · CLI + API key",
  sdk_api_key: "Fallback · SDK + API key",
  none: "Not configured",
};

export function AdminAIStatusPanel() {
  const { data, refetch, isFetching } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<AIStatus>("/ai/status"),
    staleTime: 30_000,
  });

  if (!data) {
    return (
      <Card>
        <CardBody>
          <div className="text-sm text-[var(--color-text-muted)]">Checking AI provider…</div>
        </CardBody>
      </Card>
    );
  }

  const active = data.active;
  const isUp = active === "cli_oauth" || active === "cli_api_key" || active === "sdk_api_key";

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[var(--color-text)] flex items-center gap-2">
            <Sparkles size={14} /> AI provider
          </h3>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] inline-flex items-center gap-1 disabled:opacity-50"
          >
            <RefreshCw size={11} className={isFetching ? "animate-spin" : ""} /> Recheck
          </button>
        </div>

        <div className={`flex items-center gap-2 ${statusColor[active]} text-sm font-medium`}>
          {isUp ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
          <span>{statusLabel[active]}</span>
        </div>
        <div className="text-xs text-[var(--color-text-muted)] mt-1">{data.message}</div>

        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="text-xs">
            <div className="font-semibold text-[var(--color-text-muted)] uppercase tracking-wide mb-1">
              Local CLI
            </div>
            <div>Present: {data.cli.present ? "yes" : "no"}</div>
            <div>Version: <span className="font-mono">{data.cli.version || "—"}</span></div>
            <div>OAuth logged in: {data.cli.oauth_logged_in ? "yes" : "no"}</div>
            {data.cli.auth_error && (
              <div className="text-amber-500 mt-1">{data.cli.auth_error}</div>
            )}
          </div>
          <div className="text-xs">
            <div className="font-semibold text-[var(--color-text-muted)] uppercase tracking-wide mb-1">
              API key
            </div>
            <div>
              <code className="font-mono">{data.hints.api_key_env_var}</code> set:{" "}
              {data.api_key.set ? "yes" : "no"}
            </div>
          </div>
        </div>

        {active === "none" && (
          <div className="mt-4 p-3 rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] text-xs">
            <div className="font-semibold mb-2">Enable AI</div>
            <div className="mb-2">
              <span className="font-medium">Subscription (recommended):</span> run this on the host —
            </div>
            <pre className="font-mono p-2 bg-black/40 rounded text-[11px] overflow-x-auto">
              {data.hints.subscription}
            </pre>
            <div className="mt-3 mb-2">
              <span className="font-medium">API key:</span> add to <code>.env</code> and restart backend —
            </div>
            <pre className="font-mono p-2 bg-black/40 rounded text-[11px] overflow-x-auto">
              {data.hints.api_key_env_var}=sk-ant-...
            </pre>
          </div>
        )}

        <div className="mt-3 text-[11px] text-[var(--color-text-muted)]">
          Default path is the local <code>claude</code> CLI. When both OAuth and API key are
          configured the CLI prefers OAuth (subscription). The Anthropic SDK with API key is
          used as a fallback only when the CLI is unavailable.
        </div>
      </CardBody>
    </Card>
  );
}
