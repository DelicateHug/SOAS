import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import type { TimelineEntry } from "@/types/api";

interface Props {
  caseId: string;
}

export function ChatTab({ caseId }: Props) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: timeline } = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () => api.get<TimelineEntry[]>(`/cases/${caseId}/timeline`),
    refetchInterval: 10000,
    refetchIntervalInBackground: false,
  });

  const sendMessage = useToastMutation({
    mutationFn: (content: string) =>
      api.post(`/cases/${caseId}/timeline`, {
        entry_type: "comment",
        content,
      }),
    loadingMessage: false,
    successMessage: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      setMessage("");
    },
  });

  const comments = timeline?.filter((e) => e.entry_type === "comment") || [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [comments.length]);

  return (
    <div className="flex flex-col h-[calc(100vh-20rem)]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pb-4">
        {comments.length === 0 && (
          <div className="py-12 text-center text-[hsl(var(--muted-foreground))]">
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
                <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
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
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (message.trim()) sendMessage.mutate(message.trim());
        }}
        className="flex gap-2 pt-3 border-t border-[hsl(var(--border))]"
      >
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm bg-transparent"
        />
        <button
          type="submit"
          disabled={!message.trim() || sendMessage.isPending}
          className="px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
