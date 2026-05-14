import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate, formatDateUTC } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import type { TimelineEntry } from "@/types/api";

interface Props {
  caseId: string;
}

const typeColors: Record<string, string> = {
  created: "bg-green-500",
  status_change: "bg-blue-500",
  severity_change: "bg-blue-400",
  assignment: "bg-purple-500",
  comment: "bg-gray-400",
  automation_run: "bg-cyan-500",
  automation_result: "bg-teal-500",
  evidence: "bg-amber-500",
  evidence_marked: "bg-amber-400",
  escalation: "bg-red-500",
  external_update: "bg-orange-500",
  linked: "bg-indigo-500",
  form_submission: "bg-pink-500",
  note: "bg-yellow-500",
};

export function TimelineTab({ caseId }: Props) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [excludedTypes, setExcludedTypes] = useState<Set<string>>(new Set());
  const [showUtc, setShowUtc] = useState(false);

  const { data: timeline } = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () => api.get<TimelineEntry[]>(`/cases/${caseId}/timeline`),
  });

  const uniqueTypes = useMemo(() => {
    if (!timeline) return [];
    const seen = new Set<string>();
    for (const entry of timeline) {
      seen.add(entry.entry_type);
    }
    return Array.from(seen).sort();
  }, [timeline]);

  const filteredTimeline = useMemo(() => {
    if (!timeline) return [];
    if (excludedTypes.size === 0) return timeline;
    return timeline.filter((entry) => !excludedTypes.has(entry.entry_type));
  }, [timeline, excludedTypes]);

  const toggleTypeFilter = (type: string) => {
    setExcludedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const formatTimestamp = showUtc ? formatDateUTC : formatDate;

  const addComment = useToastMutation({
    mutationFn: (content: string) =>
      api.post(`/cases/${caseId}/timeline`, {
        entry_type: "comment",
        content,
      }),
    loadingMessage: false,
    successMessage: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      setComment("");
    },
  });

  const toggleEvidence = useToastMutation({
    mutationFn: (entryId: string) =>
      api.post<TimelineEntry>(`/cases/${caseId}/timeline/${entryId}/evidence`),
    loadingMessage: "Updating evidence...",
    successMessage: "Evidence updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-notes", caseId] });
    },
  });

  return (
    <div className="space-y-4">
      {/* Add comment */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (comment.trim()) addComment.mutate(comment.trim());
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Add a comment..."
          className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
        />
        <button
          type="submit"
          disabled={!comment.trim() || addComment.isPending}
          className="px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm disabled:opacity-50"
        >
          Post
        </button>
      </form>

      {/* Filter bar */}
      {uniqueTypes.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            {uniqueTypes.map((type) => {
              const isExcluded = excludedTypes.has(type);
              return (
                <button
                  key={type}
                  onClick={() => toggleTypeFilter(type)}
                  className={`inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border transition-colors ${
                    isExcluded
                      ? "border-[var(--color-border)] text-[var(--color-text-muted)] opacity-40 line-through"
                      : "border-[var(--color-border)] text-[var(--color-text)] bg-[var(--color-surface-2)]"
                  }`}
                >
                  <span className={`inline-block h-2 w-2 rounded-full ${typeColors[type] || "bg-gray-400"} ${isExcluded ? "opacity-40" : ""}`} />
                  {type.replace(/_/g, " ")}
                </button>
              );
            })}
          </div>

          <div className="ml-auto flex items-center">
            <button
              onClick={() => setShowUtc(false)}
              className={`text-xs px-2 py-1 rounded-l border transition-colors ${
                !showUtc
                  ? "bg-[var(--color-primary)] text-[#ffffff] border-[var(--color-primary)]"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)]"
              }`}
            >
              Local
            </button>
            <button
              onClick={() => setShowUtc(true)}
              className={`text-xs px-2 py-1 rounded-r border-t border-r border-b transition-colors ${
                showUtc
                  ? "bg-[var(--color-primary)] text-[#ffffff] border-[var(--color-primary)]"
                  : "border-[var(--color-border)] text-[var(--color-text-muted)]"
              }`}
            >
              UTC
            </button>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="relative">
        {filteredTimeline.length > 0 && (
          <div className="absolute left-[15px] top-2 bottom-2 w-px bg-[var(--color-border)]" />
        )}

        <div className="space-y-0">
          {filteredTimeline.map((entry) => (
            <div key={entry.id} className="relative flex gap-3 py-3">
              <div className="relative z-10 shrink-0 mt-0.5">
                <div className={`h-[9px] w-[9px] rounded-full ring-2 ring-[var(--color-bg)] ${typeColors[entry.entry_type] || "bg-gray-400"}`} />
              </div>

              <div className="flex-1 min-w-0 -mt-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] font-medium">
                    {entry.entry_type.replace(/_/g, " ")}
                  </span>
                  {entry.is_evidence && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                      evidence
                    </span>
                  )}
                  <div className="flex items-center gap-1.5 ml-auto">
                    {entry.created_by && (
                      <div className="flex items-center gap-1">
                        <UserAvatar displayName={entry.created_by.display_name} size="sm" />
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {entry.created_by.display_name}
                        </span>
                      </div>
                    )}
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {formatTimestamp(entry.created_at)}
                    </span>
                  </div>
                </div>
                <p className="text-sm mt-1">{entry.content}</p>
                <button
                  onClick={() => toggleEvidence.mutate(entry.id)}
                  className={`mt-1.5 text-xs px-2 py-0.5 rounded border transition-colors ${
                    entry.is_evidence
                      ? "border-amber-500 text-amber-400"
                      : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-amber-400"
                  }`}
                >
                  {entry.is_evidence ? "Unmark evidence" : "Mark evidence"}
                </button>
              </div>
            </div>
          ))}
        </div>

        {timeline && timeline.length > 0 && filteredTimeline.length === 0 && (
          <div className="py-8 text-center text-[var(--color-text-muted)]">
            No matching entries — adjust filters above
          </div>
        )}

        {(!timeline || timeline.length === 0) && (
          <div className="py-8 text-center text-[var(--color-text-muted)]">
            No timeline entries yet
          </div>
        )}
      </div>
    </div>
  );
}
