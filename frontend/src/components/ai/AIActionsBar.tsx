import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

interface AIStatus {
  active: "cli_oauth" | "cli_api_key" | "sdk_api_key" | "none";
  message: string;
}

interface Action {
  id: string;
  page_key: string;
  label: string;
  icon: string | null;
  description: string | null;
  result_kind: string;
  is_enabled: boolean;
}

interface Result {
  result_kind: string;
  content: string;
  usage: { input_tokens: number; output_tokens: number };
  model: string;
}

interface Props {
  pageKey: string;
  context: Record<string, unknown>;
}

export function AIActionsBar({ pageKey, context }: Props) {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: actions = [] } = useQuery({
    queryKey: ["ai-actions", pageKey],
    queryFn: () => api.get<Action[]>(`/ai/actions?page_key=${pageKey}`),
  });

  // Probe AI status on first render so we can tell the user *why* execution will
  // fail before they click. Cached for the session.
  const { data: status } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<AIStatus>("/ai/status"),
    staleTime: 60_000,
    retry: false,
  });

  const exec = useMutation({
    mutationFn: (actionId: string) =>
      api.post<Result>(`/ai/actions/${actionId}/execute`, { context }),
    onSuccess: (r) => {
      setError(null);
      setResult(r);
    },
    onError: (e: unknown) => {
      setResult(null);
      // api.ts throws { detail?: string; error?: string; status_code?: number }, not Error.
      const err = e as { detail?: string; error?: string; message?: string };
      setError(err.detail ?? err.message ?? err.error ?? "Request failed");
    },
  });

  if (actions.length === 0) return null;

  const aiDown = status && status.active === "none";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((a) => (
          <button
            key={a.id}
            onClick={() => exec.mutate(a.id)}
            disabled={exec.isPending || aiDown}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
            title={aiDown ? "AI is not configured — see Danger Zone → AI provider" : a.description ?? ""}
          >
            <Sparkles size={12} className="text-[var(--color-sidebar-accent)]" />
            {a.label}
          </button>
        ))}
        {aiDown && (
          <Link
            to="/admin/danger-zone"
            className="inline-flex items-center gap-1 text-xs text-amber-500 hover:underline"
            title="Configure AI"
          >
            <AlertCircle size={12} />
            AI not configured
          </Link>
        )}
      </div>
      {(result || error) && (
        <Card>
          <CardBody>
            {error && (
              <div className="text-xs">
                <div className="text-[var(--color-danger)] font-medium mb-1 flex items-center gap-1">
                  <AlertCircle size={12} /> AI action failed
                </div>
                <div className="text-[var(--color-text-muted)] whitespace-pre-wrap">{error}</div>
              </div>
            )}
            {result && (
              <>
                <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
                  {result.model} · {result.usage.input_tokens + result.usage.output_tokens} tokens
                </div>
                <pre className="text-xs whitespace-pre-wrap font-sans">{result.content}</pre>
              </>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
