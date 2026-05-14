import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

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

  const exec = useMutation({
    mutationFn: (actionId: string) =>
      api.post<Result>(`/ai/actions/${actionId}/execute`, { context }),
    onSuccess: (r) => {
      setError(null);
      setResult(r);
    },
    onError: (e: Error) => {
      setResult(null);
      setError(e.message);
    },
  });

  if (actions.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <button
            key={a.id}
            onClick={() => exec.mutate(a.id)}
            disabled={exec.isPending}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-primary)] disabled:opacity-50"
            title={a.description ?? ""}
          >
            <Sparkles size={12} className="text-[var(--color-sidebar-accent)]" />
            {a.label}
          </button>
        ))}
      </div>
      {(result || error) && (
        <Card>
          <CardBody>
            {error && <div className="text-xs text-[var(--color-danger)] font-mono">{error}</div>}
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
