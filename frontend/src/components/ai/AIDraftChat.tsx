/**
 * Generic multi-turn drafting chat.
 *
 * Used by:
 *   - Saved Queries → New Query modal (`kind="query"`)
 *   - Code Library → New Code Block modal (`kind="code"`)
 *
 * The backend's `/ai/draft-chat` endpoint emits a fenced ```<tag>...``` block
 * tagged with the dialect's natural language (`query` or `code`). We extract
 * the latest one and surface it as the "Suggested …" field with Copy and a
 * "Use this …" button that calls `onApply` so the parent form's textarea is
 * filled.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { marked } from "marked";
import {
  Send, Loader2, Sparkles, Copy, Check, ArrowDownToLine,
  AlertCircle, Trash2, X as XIcon,
} from "lucide-react";
import { api } from "@/lib/api";

interface AIStatus {
  active: "cli_oauth" | "cli_api_key" | "sdk_api_key" | "none";
}

interface PatchOp {
  op: "replace" | "insert_after" | "insert_before" | "delete";
  find: string;
  with?: string;
}

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  suggested?: string | null;
  patch?: PatchOp[] | null;
  ts: number;
}

interface ChatResponse {
  content: string;
  suggested: string | null;
  patch: PatchOp[] | null;
  fence_tag: string;
  usage: { input_tokens: number; output_tokens: number };
  model: string;
}

export type DraftKind = "query" | "code";

interface TargetOption {
  value: string;
  label: string;
}

const TARGETS_BY_KIND: Record<DraftKind, TargetOption[]> = {
  query: [
    { value: "incidents_sql", label: "Postgres / SOAS schema" },
    { value: "kql", label: "Microsoft Defender / Sentinel (KQL)" },
    { value: "leql", label: "Rapid7 InsightIDR (LEQL)" },
    { value: "splunk", label: "Splunk (SPL)" },
    { value: "winevent", label: "Windows Event Logs" },
    { value: "sysmon", label: "Sysmon" },
  ],
  code: [{ value: "code_python", label: "Python (Visual Python block)" }],
};

const SUGGESTED_LABEL: Record<DraftKind, string> = {
  query: "Suggested query",
  code: "Suggested code",
};

const USE_LABEL: Record<DraftKind, string> = {
  query: "Use this query",
  code: "Use this code",
};

const EMPTY_HINT: Record<DraftKind, string> = {
  query: "Describe what you want to hunt for — e.g. \"failed sign-ins from new IPs in the last 24h\"",
  code: "Describe what you want the code block to do — e.g. \"normalize an email header and split into domain/local parts\"",
};

interface Props {
  kind: DraftKind;
  /** Pre-selected target type. */
  initialTarget?: string;
  /** Called when the analyst clicks "Use this …" (full replace). */
  onApply: (text: string) => void;
  /** Called when applying a targeted patch returned from the model. The current
   * draft is provided so the caller can re-derive whatever in-memory state
   * needs to update. Returns the new text. */
  onApplyPatch?: (patched: string) => void;
  /** Returns the most recent editor state to send as context to the model.
   * Called fresh on every `Send` so the model always sees current state. */
  getContext?: () => Record<string, unknown>;
}

export function AIDraftChat({ kind, initialTarget, onApply, onApplyPatch, getContext }: Props) {
  const targets = TARGETS_BY_KIND[kind];
  const [target, setTarget] = useState<string>(initialTarget ?? targets[0].value);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [copied, setCopied] = useState(false);
  // Once the user applies or dismisses a panel, remember the ts so it stays
  // hidden until the next assistant turn produces a newer one.
  const [dismissedPatchTs, setDismissedPatchTs] = useState(0);
  const [dismissedSuggestedTs, setDismissedSuggestedTs] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: status } = useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<AIStatus>("/ai/status"),
    staleTime: 60_000,
    retry: false,
  });
  const aiDown = status && status.active === "none";

  const chat = useMutation({
    mutationFn: (history: ChatTurn[]) =>
      api.post<ChatResponse>("/ai/draft-chat", {
        target_type: target,
        messages: history.map((m) => ({ role: m.role, content: m.content })),
        context: getContext ? getContext() : undefined,
      }),
    onSuccess: (r) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: r.content,
          suggested: r.suggested,
          patch: r.patch,
          ts: Date.now(),
        },
      ]);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, chat.isPending]);

  const send = () => {
    const text = input.trim();
    if (!text || chat.isPending) return;
    const next: ChatTurn = { role: "user", content: text, ts: Date.now() };
    const history = [...messages, next];
    setMessages(history);
    setInput("");
    chat.mutate(history);
  };

  const reset = () => {
    setMessages([]);
    setInput("");
  };

  const latestSuggestedTurn = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && m.suggested);
  const latest =
    latestSuggestedTurn && latestSuggestedTurn.ts > dismissedSuggestedTs
      ? latestSuggestedTurn.suggested ?? null
      : null;

  const latestPatchTurn = [...messages]
    .reverse()
    .find((m) => m.role === "assistant" && m.patch && m.patch.length > 0);
  const latestPatch =
    latestPatchTurn && latestPatchTurn.ts > dismissedPatchTs
      ? latestPatchTurn.patch ?? null
      : null;

  /** Apply a list of patch ops against the current draft (from getContext) and
   * call onApplyPatch with the result. Returns the new text + a list of ops that
   * failed to match (so the UI can show them). */
  const applyPatch = (ops: PatchOp[]): { next: string; failed: PatchOp[] } => {
    const ctx = getContext ? getContext() : {};
    const draftKey = (["code", "query_text", "draft", "content"] as const).find(
      (k) => k in ctx
    );
    let text = draftKey ? String(ctx[draftKey] ?? "") : "";
    const failed: PatchOp[] = [];
    for (const op of ops) {
      if (!text.includes(op.find)) {
        failed.push(op);
        continue;
      }
      if (op.op === "replace") {
        text = text.replace(op.find, op.with ?? "");
      } else if (op.op === "insert_after") {
        text = text.replace(op.find, op.find + (op.with ?? ""));
      } else if (op.op === "insert_before") {
        text = text.replace(op.find, (op.with ?? "") + op.find);
      } else if (op.op === "delete") {
        text = text.replace(op.find, "");
      }
    }
    return { next: text, failed };
  };

  const copyLatest = () => {
    if (!latest) return;
    navigator.clipboard.writeText(latest).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  };

  const errorMsg = chat.error
    ? ((chat.error as unknown as { detail?: string; message?: string }).detail ??
       (chat.error as Error).message ??
       "Request failed")
    : null;

  return (
    <div className="border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] flex flex-col overflow-hidden">
      <style>{`
        .ai-markdown { color: var(--color-text); }
        .ai-markdown p { margin: 0 0 0.5em 0; color: var(--color-text); }
        .ai-markdown p:last-child { margin-bottom: 0; }
        .ai-markdown ul, .ai-markdown ol { margin: 0 0 0.5em 0; padding-left: 1.25em; color: var(--color-text); }
        .ai-markdown li { margin: 0.1em 0; }
        .ai-markdown strong { font-weight: 600; color: var(--color-text); }
        .ai-markdown em { color: var(--color-text); }
        /* Inline code: high-contrast pill that doesn't disappear on either theme. */
        .ai-markdown code {
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
          background: rgba(127, 127, 127, 0.18);
          color: var(--color-text);
          padding: 0.08em 0.35em;
          border-radius: 3px;
          font-size: 0.92em;
          border: 1px solid rgba(127, 127, 127, 0.18);
        }
        .ai-markdown pre {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          color: var(--color-text);
          border-radius: 4px;
          padding: 0.5em 0.6em;
          overflow-x: auto;
          margin: 0.4em 0;
          font-size: 0.92em;
        }
        .ai-markdown pre code {
          background: transparent;
          border: 0;
          padding: 0;
          color: var(--color-text);
        }
        .ai-markdown h1, .ai-markdown h2, .ai-markdown h3 {
          font-weight: 600;
          margin: 0.6em 0 0.3em 0;
          font-size: 1em;
          color: var(--color-text);
        }
        .ai-markdown a { color: var(--color-primary); text-decoration: underline; }
        .ai-markdown blockquote {
          border-left: 2px solid var(--color-border);
          padding-left: 0.6em;
          color: var(--color-text-muted);
          margin: 0.4em 0;
        }
      `}</style>

      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface-2)]">
        <div className="flex items-center gap-2 text-xs font-medium">
          <Sparkles size={14} className="text-[var(--color-primary)]" />
          Build with AI
        </div>
        <div className="flex items-center gap-2">
          {targets.length > 1 && (
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="px-2 py-1 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)] text-[var(--color-text)]"
              disabled={chat.isPending}
            >
              {targets.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          )}
          {messages.length > 0 && (
            <button
              onClick={reset}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-bg)]"
              title="Clear chat"
            >
              <Trash2 size={11} />
              Reset
            </button>
          )}
        </div>
      </div>

      {aiDown && (
        <div className="px-3 py-2 text-xs text-amber-500 flex items-center gap-1.5 border-b border-[var(--color-border)]">
          <AlertCircle size={12} />
          AI is not configured. Visit Danger Zone → AI provider to enable it.
        </div>
      )}

      {latestPatch && (
        <div className="border-b border-[var(--color-border)] px-3 py-2 bg-[var(--color-bg)]">
          <div className="flex items-center justify-between mb-1">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] font-semibold">
              Targeted edit ({latestPatch.length} {latestPatch.length === 1 ? "op" : "ops"})
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  const { next, failed } = applyPatch(latestPatch);
                  if (failed.length > 0 && failed.length === latestPatch.length) {
                    window.alert(
                      "Couldn't apply the patch — none of the find strings matched the current draft. " +
                      "Ask the AI to retry."
                    );
                    return;
                  }
                  if (onApplyPatch) onApplyPatch(next);
                  else onApply(next);
                  // Auto-dismiss so a successfully-applied patch doesn't linger.
                  if (latestPatchTurn) setDismissedPatchTs(latestPatchTurn.ts);
                  if (failed.length > 0) {
                    window.alert(
                      `${failed.length} of ${latestPatch.length} ops didn't match and were skipped.`
                    );
                  }
                }}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[var(--color-primary)] text-white hover:opacity-90"
                title="Apply targeted edit to the current draft"
              >
                <ArrowDownToLine size={11} />
                Apply edit
              </button>
              <button
                onClick={() => latestPatchTurn && setDismissedPatchTs(latestPatchTurn.ts)}
                className="p-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                title="Dismiss"
                aria-label="Dismiss"
              >
                <XIcon size={11} />
              </button>
            </div>
          </div>
          <div className="space-y-1 max-h-40 overflow-auto">
            {latestPatch.map((op, i) => (
              <div key={i} className="text-[11px] font-mono">
                <span className="text-[var(--color-primary)] font-semibold">{op.op}</span>
                {": "}
                <span className="text-[var(--color-text-muted)]">find</span>{" "}
                <code className="bg-[var(--color-surface)] px-1 rounded">{(op.find || "").slice(0, 60)}{(op.find || "").length > 60 ? "…" : ""}</code>
                {op.with !== undefined && (
                  <>
                    {" "}
                    <span className="text-[var(--color-text-muted)]">with</span>{" "}
                    <code className="bg-[var(--color-surface)] px-1 rounded">{op.with.slice(0, 60)}{op.with.length > 60 ? "…" : ""}</code>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {latest && (
        <div className="border-b border-[var(--color-border)] px-3 py-2 bg-[var(--color-bg)]">
          <div className="flex items-center justify-between mb-1">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] font-semibold">
              {SUGGESTED_LABEL[kind]}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={copyLatest}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                title="Copy to clipboard"
              >
                {copied ? <Check size={11} className="text-emerald-500" /> : <Copy size={11} />}
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                onClick={() => {
                  onApply(latest);
                  if (latestSuggestedTurn) setDismissedSuggestedTs(latestSuggestedTurn.ts);
                }}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[var(--color-primary)] text-white hover:opacity-90"
                title={`Fill the ${kind} field`}
              >
                <ArrowDownToLine size={11} />
                {USE_LABEL[kind]}
              </button>
              <button
                onClick={() => latestSuggestedTurn && setDismissedSuggestedTs(latestSuggestedTurn.ts)}
                className="p-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                title="Dismiss"
                aria-label="Dismiss"
              >
                <XIcon size={11} />
              </button>
            </div>
          </div>
          <pre className="font-mono text-[11px] whitespace-pre-wrap text-[var(--color-text)] bg-[var(--color-surface)] border border-[var(--color-border)] rounded px-2 py-1.5 max-h-40 overflow-auto">
            {latest}
          </pre>
        </div>
      )}

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-3 min-h-[180px] max-h-[40vh]"
      >
        {messages.length === 0 && !chat.isPending && (
          <div className="text-xs text-[var(--color-text-muted)] text-center py-6 italic">
            {EMPTY_HINT[kind]}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-lg px-3 py-1.5 bg-[var(--color-primary)] text-white text-xs whitespace-pre-wrap">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div
                className="max-w-[85%] rounded-lg px-3 py-1.5 bg-[var(--color-surface-2)] text-[var(--color-text)] text-xs ai-markdown"
                dangerouslySetInnerHTML={{
                  __html: marked.parse(m.content || "", { async: false }) as string,
                }}
              />
            </div>
          )
        )}
        {chat.isPending && (
          <div className="flex justify-start">
            <div className="rounded-lg px-3 py-1.5 bg-[var(--color-surface-2)] text-[var(--color-text-muted)] text-xs flex items-center gap-2">
              <Loader2 size={12} className="animate-spin" />
              Thinking…
            </div>
          </div>
        )}
        {errorMsg && (
          <div className="text-xs rounded border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/5 px-2 py-1.5">
            <div className="text-[var(--color-danger)] font-medium flex items-center gap-1 mb-0.5">
              <AlertCircle size={12} /> AI request failed
            </div>
            <div className="text-[var(--color-text-muted)] whitespace-pre-wrap">{errorMsg}</div>
          </div>
        )}
      </div>

      <div className="border-t border-[var(--color-border)] p-2 flex gap-2 bg-[var(--color-bg)]">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={aiDown ? "AI is not configured" : "Type a message — Enter to send, Shift+Enter for newline"}
          rows={2}
          disabled={aiDown || chat.isPending}
          className="flex-1 px-2 py-1.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] resize-y disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={aiDown || chat.isPending || !input.trim()}
          className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded bg-[var(--color-primary)] text-white hover:opacity-90 disabled:opacity-50 self-end"
        >
          {chat.isPending ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          Send
        </button>
      </div>
    </div>
  );
}
