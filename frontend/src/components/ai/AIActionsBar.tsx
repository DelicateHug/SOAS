import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles, AlertCircle, ChevronDown, Send, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

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
  const [activeAction, setActiveAction] = useState<Action | null>(null);
  const [userPrompt, setUserPrompt] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: actions = [] } = useQuery({
    queryKey: ["ai-actions", pageKey],
    queryFn: () => api.get<Action[]>(`/ai/actions?page_key=${pageKey}`),
  });

  const { data: status } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<AIStatus>("/ai/status"),
    staleTime: 60_000,
    retry: false,
  });

  const exec = useMutation({
    mutationFn: ({ actionId, prompt }: { actionId: string; prompt: string }) =>
      api.post<Result>(`/ai/actions/${actionId}/execute`, {
        context,
        user_prompt: prompt || null,
      }),
    onSuccess: (r) => {
      setError(null);
      setResult(r);
    },
    onError: (e: unknown) => {
      setResult(null);
      const err = e as { detail?: string; error?: string; message?: string };
      setError(err.detail ?? err.message ?? err.error ?? "Request failed");
    },
  });

  if (actions.length === 0) return null;

  const aiDown = status && status.active === "none";

  const pickAction = (a: Action) => {
    setActiveAction(a);
    setResult(null);
    setError(null);
    setUserPrompt("");
  };

  const run = () => {
    if (!activeAction) return;
    exec.mutate({ actionId: activeAction.id, prompt: userPrompt });
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((a) => {
          const isActive = activeAction?.id === a.id;
          return (
            <button
              key={a.id}
              onClick={() => pickAction(a)}
              disabled={aiDown}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                isActive
                  ? "border-[var(--color-primary)] bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                  : "border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-primary)]"
              }`}
              title={aiDown ? "AI is not configured — see Danger Zone → AI provider" : a.description ?? ""}
            >
              <Sparkles size={12} className="text-[var(--color-sidebar-accent)]" />
              {a.label}
            </button>
          );
        })}
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

      {activeAction && !aiDown && (
        <div className="border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] p-3 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-[var(--color-text)]">
                {activeAction.label}
              </div>
              {activeAction.description && (
                <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                  {activeAction.description}
                </div>
              )}
            </div>
            <button
              onClick={() => {
                setActiveAction(null);
                setResult(null);
                setError(null);
              }}
              className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              title="Close"
            >
              <ChevronDown size={14} />
            </button>
          </div>
          <textarea
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                run();
              }
            }}
            placeholder="Optional: describe what you want…  (Ctrl+Enter to run)"
            rows={3}
            className="w-full px-2 py-1.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] font-sans resize-y"
          />
          <div className="flex items-center justify-between">
            <div className="text-[10px] text-[var(--color-text-muted)]">
              Page context attached automatically.
            </div>
            <button
              onClick={run}
              disabled={exec.isPending}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50"
            >
              {exec.isPending ? (
                <>
                  <Loader2 size={12} className="animate-spin" /> Running…
                </>
              ) : (
                <>
                  <Send size={12} /> Run
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="text-xs rounded border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/5 px-2 py-1.5">
              <div className="text-[var(--color-danger)] font-medium flex items-center gap-1 mb-0.5">
                <AlertCircle size={12} /> AI action failed
              </div>
              <div className="text-[var(--color-text-muted)] whitespace-pre-wrap">{error}</div>
            </div>
          )}

          {result && (
            <div className="text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] mb-1.5">
                {result.model} · {result.usage.input_tokens + result.usage.output_tokens} tokens
              </div>
              <div className="whitespace-pre-wrap font-sans text-[var(--color-text)] leading-relaxed">
                {result.content}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
