/**
 * Multi-turn query-builder chat.
 *
 * Mounted inside the New Query modal. The analyst types in plain English,
 * the model asks clarifying questions and emits a `query` fenced block at
 * the end of every reply. We extract that block into a "Suggested query"
 * field with copy + "Use this query" buttons; clicking the latter calls
 * `onApply(query)` so the parent form's textarea is filled.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { marked } from "marked";
import { Send, Loader2, Sparkles, Copy, Check, ArrowDownToLine, AlertCircle, Trash2 } from "lucide-react";
import { api } from "@/lib/api";

interface AIStatus {
  active: "cli_oauth" | "cli_api_key" | "sdk_api_key" | "none";
}

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  suggested_query?: string | null;
  ts: number;
}

interface ChatResponse {
  content: string;
  suggested_query: string | null;
  usage: { input_tokens: number; output_tokens: number };
  model: string;
}

const TARGET_OPTIONS = [
  { value: "incidents_sql", label: "Postgres / SOAS schema" },
  { value: "kql", label: "Microsoft Defender / Sentinel (KQL)" },
  { value: "leql", label: "Rapid7 InsightIDR (LEQL)" },
  { value: "splunk", label: "Splunk (SPL)" },
  { value: "winevent", label: "Windows Event Logs" },
  { value: "sysmon", label: "Sysmon" },
] as const;

interface Props {
  /** Pre-selected target type from the parent form. */
  initialTarget?: string;
  /** Called when the analyst clicks "Use this query". */
  onApply: (query: string) => void;
}

export function AIQueryChat({ initialTarget = "incidents_sql", onApply }: Props) {
  const [target, setTarget] = useState<string>(initialTarget);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [copied, setCopied] = useState(false);
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
      api.post<ChatResponse>("/ai/query-chat", {
        target_type: target,
        messages: history.map((m) => ({ role: m.role, content: m.content })),
      }),
    onSuccess: (r) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: r.content,
          suggested_query: r.suggested_query,
          ts: Date.now(),
        },
      ]);
    },
  });

  // Auto-scroll to bottom on new messages
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

  // Most-recent suggested query (any assistant turn, last one wins)
  const latestQuery = [...messages].reverse().find((m) => m.role === "assistant" && m.suggested_query)?.suggested_query ?? null;

  const copyQuery = () => {
    if (!latestQuery) return;
    navigator.clipboard.writeText(latestQuery).then(() => {
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
        .ai-markdown p { margin: 0 0 0.5em 0; }
        .ai-markdown p:last-child { margin-bottom: 0; }
        .ai-markdown ul, .ai-markdown ol { margin: 0 0 0.5em 0; padding-left: 1.25em; }
        .ai-markdown li { margin: 0.1em 0; }
        .ai-markdown strong { font-weight: 600; }
        .ai-markdown code {
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
          background: var(--color-bg);
          padding: 0.05em 0.3em;
          border-radius: 3px;
          font-size: 0.92em;
        }
        .ai-markdown pre {
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 4px;
          padding: 0.5em 0.6em;
          overflow-x: auto;
          margin: 0.4em 0;
          font-size: 0.92em;
        }
        .ai-markdown pre code { background: transparent; padding: 0; }
        .ai-markdown h1, .ai-markdown h2, .ai-markdown h3 {
          font-weight: 600;
          margin: 0.6em 0 0.3em 0;
          font-size: 1em;
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
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="px-2 py-1 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)] text-[var(--color-text)]"
            disabled={chat.isPending}
          >
            {TARGET_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
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

      {/* Suggested query */}
      {latestQuery && (
        <div className="border-b border-[var(--color-border)] px-3 py-2 bg-[var(--color-bg)]">
          <div className="flex items-center justify-between mb-1">
            <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] font-semibold">
              Suggested query
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={copyQuery}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                title="Copy to clipboard"
              >
                {copied ? <Check size={11} className="text-emerald-500" /> : <Copy size={11} />}
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                onClick={() => onApply(latestQuery)}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded bg-[var(--color-primary)] text-white hover:opacity-90"
                title="Fill the Query field below"
              >
                <ArrowDownToLine size={11} />
                Use this query
              </button>
            </div>
          </div>
          <pre className="font-mono text-[11px] whitespace-pre-wrap text-[var(--color-text)] bg-[var(--color-surface)] border border-[var(--color-border)] rounded px-2 py-1.5 max-h-40 overflow-auto">
            {latestQuery}
          </pre>
        </div>
      )}

      {/* Transcript */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-3 min-h-[180px] max-h-[40vh]"
      >
        {messages.length === 0 && !chat.isPending && (
          <div className="text-xs text-[var(--color-text-muted)] text-center py-6">
            Describe what you want to hunt for — e.g.&nbsp;
            <span className="italic">
              "successful logins from new IPs in the last 24h"
            </span>
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

      {/* Input */}
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
