import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { WriteGuard } from "@/components/work/WriteGuard";
import type { TimelineEntry } from "@/types/api";

interface Props {
  incidentId: string;
}

export function ChatTab({ incidentId }: Props) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: timeline } = useQuery({
    queryKey: ["incident-timeline", incidentId],
    queryFn: () => api.get<TimelineEntry[]>(`/incidents/${incidentId}/timeline`),
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  });

  const sendMessage = useToastMutation({
    mutationFn: (content: string) =>
      api.post(`/incidents/${incidentId}/timeline`, {
        entry_type: "comment",
        content,
      }),
    loadingMessage: false,
    successMessage: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", incidentId] });
      setMessage("");
    },
  });

  // Filter to only comments
  const comments = timeline?.filter((e) => e.entry_type === "comment") || [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [comments.length]);

  return (
    <div className="flex flex-col h-[calc(100vh-20rem)]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pb-4">
        {comments.length === 0 && (
          <div className="py-12 text-center text-[var(--color-text-muted)]">
            No messages yet. Start the conversation.
          </div>
        )}
        {comments.map((entry) => (
          <div key={entry.id} className="flex gap-2.5">
            <UserAvatar
              displayName={entry.created_by?.display_name || "System"}
              size="sm"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-medium">
                  {entry.created_by?.display_name || "System"}
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  {formatDate(entry.created_at)}
                </span>
              </div>
              <p className="text-sm mt-0.5 whitespace-pre-wrap">{entry.content}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <WriteGuard blockedTitle="Start work on this incident to send chat messages">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (message.trim()) sendMessage.mutate(message.trim());
          }}
          className="flex gap-2 pt-3 border-t border-[var(--color-border)]"
        >
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
          />
          <button
            type="submit"
            disabled={!message.trim() || sendMessage.isPending}
            className="px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </WriteGuard>
    </div>
  );
}
