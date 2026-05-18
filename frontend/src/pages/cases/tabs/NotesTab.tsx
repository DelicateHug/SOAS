import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { WriteGuard } from "@/components/work/WriteGuard";
import type { CaseNote } from "@/types/api";

interface Props {
  caseId: string;
}

export function NotesTab({ caseId }: Props) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: notes } = useQuery({
    queryKey: ["case-notes", caseId],
    queryFn: () => api.get<CaseNote[]>(`/cases/${caseId}/notes`),
  });

  const createNote = useToastMutation({
    mutationFn: (content: string) =>
      api.post(`/cases/${caseId}/notes`, { content }),
    loadingMessage: "Saving note...",
    successMessage: "Note saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-notes", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      setNewNote("");
      setShowForm(false);
    },
  });

  const updateNote = useToastMutation({
    mutationFn: ({ noteId, content }: { noteId: string; content: string }) =>
      api.patch(`/cases/${caseId}/notes/${noteId}`, { content }),
    loadingMessage: "Saving note...",
    successMessage: "Note saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-notes", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      setEditingId(null);
    },
  });

  const deleteNote = useToastMutation({
    mutationFn: (noteId: string) =>
      api.delete(`/cases/${caseId}/notes/${noteId}`),
    loadingMessage: "Deleting note...",
    successMessage: "Note deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-notes", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
    },
  });

  const toggleEvidence = useToastMutation({
    mutationFn: (noteId: string) =>
      api.post<CaseNote>(`/cases/${caseId}/notes/${noteId}/evidence`),
    loadingMessage: "Updating evidence...",
    successMessage: "Evidence updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-notes", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
    },
  });

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Notes"
        action={
          !showForm ? (
            <WriteGuard blockedTitle="Start work on this group to add notes">
              <button
                onClick={() => setShowForm(true)}
                className="px-3 py-1.5 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-xs font-medium"
              >
                Add Note
              </button>
            </WriteGuard>
          ) : undefined
        }
      />

      {showForm && (
        <WriteGuard blockedTitle="Start work on this group to add notes">
          <div className="rounded-lg border border-[var(--color-border)] p-4">
            <textarea
              value={newNote}
              onChange={(e) => setNewNote(e.target.value)}
              placeholder="Write your note..."
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm min-h-24 resize-y bg-transparent"
            />
            <div className="flex gap-2 mt-2">
              <button
                onClick={() => newNote.trim() && createNote.mutate(newNote.trim())}
                disabled={!newNote.trim() || createNote.isPending}
                className="px-4 py-1.5 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => { setShowForm(false); setNewNote(""); }}
                className="px-4 py-1.5 border border-[var(--color-border)] rounded-md text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </WriteGuard>
      )}

      <div className="space-y-3">
        {notes?.map((note) => (
          <div key={note.id} className="rounded-lg border border-[var(--color-border)] p-4">
            {editingId === note.id ? (
              <div>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-sm min-h-20 resize-y bg-transparent"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() =>
                      editContent.trim() &&
                      updateNote.mutate({ noteId: note.id, content: editContent.trim() })
                    }
                    className="px-3 py-1 bg-[var(--color-primary)] text-[#ffffff] rounded text-sm"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1 border border-[var(--color-border)] rounded text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <UserAvatar displayName={note.created_by.display_name} size="sm" />
                  <span className="text-xs font-medium">{note.created_by.display_name}</span>
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {formatDate(note.created_at)}
                  </span>
                  {note.is_evidence && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                      evidence
                    </span>
                  )}
                  <div className="ml-auto flex gap-1">
                    <button
                      onClick={() => toggleEvidence.mutate(note.id)}
                      className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                        note.is_evidence
                          ? "border-amber-500 text-amber-400"
                          : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-amber-400"
                      }`}
                    >
                      {note.is_evidence ? "Unmark" : "Evidence"}
                    </button>
                    <button
                      onClick={() => { setEditingId(note.id); setEditContent(note.content); }}
                      className="text-xs px-2 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => { if (confirm("Delete this note?")) deleteNote.mutate(note.id); }}
                      className="text-xs px-2 py-0.5 rounded border border-[var(--color-border)] text-red-400 hover:text-red-300"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <p className="text-sm whitespace-pre-wrap">{note.content}</p>
              </>
            )}
          </div>
        ))}
        {(!notes || notes.length === 0) && !showForm && (
          <div className="py-8 text-center text-[var(--color-text-muted)]">
            No notes yet
          </div>
        )}
      </div>
    </div>
  );
}
