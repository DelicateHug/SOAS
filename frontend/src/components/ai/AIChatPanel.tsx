import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Send, Star, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  ts: string;
}

interface Chat {
  id: string;
  name: string;
  transcript: ChatTurn[];
  model: string | null;
  is_favorite: boolean;
  token_total: number;
  case_id: string | null;
  incident_id: string | null;
}

interface Props {
  caseId?: string;
  incidentId?: string;
}

export function AIChatPanel({ caseId, incidentId }: Props) {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [model, setModel] = useState<"opus" | "sonnet" | "haiku">("sonnet");

  const queryKey = ["ai-chats", caseId ?? null, incidentId ?? null];
  const { data: chats = [] } = useQuery({
    queryKey,
    queryFn: () => {
      const params = new URLSearchParams();
      if (caseId) params.set("case_id", caseId);
      if (incidentId) params.set("incident_id", incidentId);
      return api.get<Chat[]>(`/ai/chats?${params.toString()}`);
    },
  });

  const create = useMutation({
    mutationFn: (name: string) =>
      api.post<Chat>("/ai/chats", { name, case_id: caseId, incident_id: incidentId, model }),
    onSuccess: (chat) => {
      qc.invalidateQueries({ queryKey });
      setActiveId(chat.id);
    },
  });
  const send = useMutation({
    mutationFn: ({ chatId, content }: { chatId: string; content: string }) =>
      api.post<Chat>(`/ai/chats/${chatId}/send`, { content, model }),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/ai/chats/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      setActiveId(null);
    },
  });

  const active = chats.find((c) => c.id === activeId) ?? null;

  return (
    <div className="grid grid-cols-12 gap-3 h-[600px]">
      <div className="col-span-3 flex flex-col gap-2">
        <button
          onClick={() => {
            const name = prompt("Chat name?");
            if (name) create.mutate(name);
          }}
          className="inline-flex items-center justify-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
        >
          <Plus size={12} /> New chat
        </button>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value as "opus" | "sonnet" | "haiku")}
          className="px-2 py-1 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
        >
          <option value="opus">Opus 4.7</option>
          <option value="sonnet">Sonnet 4.6</option>
          <option value="haiku">Haiku 4.5</option>
        </select>
        <div className="flex-1 overflow-auto space-y-1">
          {chats.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveId(c.id)}
              className={`w-full text-left px-2 py-1.5 rounded text-xs ${
                activeId === c.id ? "bg-[var(--color-surface-2)]" : "hover:bg-[var(--color-surface-subtle)]"
              }`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="truncate flex-1 text-[var(--color-text)]">{c.name}</span>
                {c.is_favorite && <Star size={10} fill="var(--color-warning)" className="text-[var(--color-warning)]" />}
              </div>
              <div className="text-[10px] font-mono text-[var(--color-text-muted)] mt-0.5">
                {c.transcript.length} turns · {c.token_total.toLocaleString()} tok
              </div>
            </button>
          ))}
        </div>
      </div>
      <div className="col-span-9">
        {active ? (
          <Card className="h-full flex flex-col">
            <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center justify-between">
              <div className="text-sm font-semibold">{active.name}</div>
              <button onClick={() => confirm("Delete chat?") && remove.mutate(active.id)} className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]">
                <Trash2 size={12} />
              </button>
            </div>
            <div className="flex-1 overflow-auto p-3 space-y-3">
              {active.transcript.length === 0 ? (
                <div className="text-xs text-[var(--color-text-muted)] py-12 text-center">
                  Send a message to start the conversation.
                </div>
              ) : (
                active.transcript.map((t, i) => (
                  <div
                    key={i}
                    className={`text-sm ${t.role === "user" ? "" : "bg-[var(--color-surface-2)] p-2.5 rounded"}`}
                  >
                    <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] mb-0.5">{t.role}</div>
                    <div className="whitespace-pre-wrap">{t.content}</div>
                  </div>
                ))
              )}
            </div>
            <div className="border-t border-[var(--color-border)] p-2 flex gap-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type a message…"
                rows={2}
                className="flex-1 px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] resize-none"
              />
              <button
                onClick={() => {
                  if (draft.trim()) {
                    send.mutate({ chatId: active.id, content: draft.trim() });
                    setDraft("");
                  }
                }}
                disabled={send.isPending || !draft.trim()}
                className="px-3 rounded bg-[var(--color-primary)] text-white disabled:opacity-50"
              >
                <Send size={14} />
              </button>
            </div>
          </Card>
        ) : (
          <Card className="h-full">
            <CardBody className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">
              Pick a chat from the left, or create a new one.
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
