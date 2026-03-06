import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { formatDate } from "@/lib/utils";
import { Send, Trash2, Edit3, Check, X, ShieldCheck } from "lucide-react";
import type { IssueNote } from "@/types/api";

interface Props {
  issueId: string;
  issueCreatorId: string;
}

export function NotesTab({ issueId, issueCreatorId }: Props) {
  const { user, hasPermission } = useAuthStore();
  const queryClient = useQueryClient();
  const [newNote, setNewNote] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: notes, isLoading } = useQuery({
    queryKey: ["issue-notes", issueId],
    queryFn: () => api.get<IssueNote[]>(`/issues/${issueId}/notes`),
  });

  const createNote = useToastMutation({
    mutationFn: () =>
      api.post(`/issues/${issueId}/notes`, { content: newNote }),
    loadingMessage: "Saving note...",
    successMessage: "Note saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
      setNewNote("");
    },
  });

  const updateNote = useToastMutation({
    mutationFn: (noteId: string) =>
      api.patch(`/issues/${issueId}/notes/${noteId}`, { content: editContent }),
    loadingMessage: "Saving note...",
    successMessage: "Note saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
      setEditingId(null);
    },
  });

  const deleteNote = useToastMutation({
    mutationFn: (noteId: string) =>
      api.request(`/issues/${issueId}/notes/${noteId}`, { method: "DELETE" }),
    loadingMessage: "Deleting note...",
    successMessage: "Note deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
    },
  });

  const toggleEvidence = useToastMutation({
    mutationFn: (noteId: string) =>
      api.post(`/issues/${issueId}/notes/${noteId}/evidence`, {}),
    loadingMessage: "Updating evidence...",
    successMessage: "Evidence updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
    },
  });

  const canModifyNote = (note: IssueNote) =>
    note.created_by.id === user?.id ||
    user?.id === issueCreatorId ||
    hasPermission("issue:update");

  const canDeleteNote = (note: IssueNote) =>
    note.created_by.id === user?.id ||
    hasPermission("issue:delete");

  return (
    <div>
      {/* Create note */}
      <div className="flex gap-2 mb-4">
        <textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Add a note... (evidence = progress made, general = chat)"
          rows={2}
          className="flex-1 px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm resize-y"
        />
        <button
          onClick={() => createNote.mutate()}
          disabled={!newNote.trim() || createNote.isPending}
          className="px-3 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md disabled:opacity-50 self-end"
          title="Submit note"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>

      {/* Notes list */}
      {isLoading ? (
        <div className="text-center py-4 text-sm">Loading notes...</div>
      ) : notes?.length === 0 ? (
        <p className="text-sm text-[hsl(var(--muted-foreground))] italic text-center py-4">
          No notes yet.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {notes?.map((note) => (
            <div
              key={note.id}
              className={`border rounded-lg p-3 ${
                note.is_evidence
                  ? "border-green-500/30 bg-green-500/5"
                  : "border-[hsl(var(--border))]"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                  <span className="font-medium text-[hsl(var(--foreground))]">
                    {note.created_by.display_name}
                  </span>
                  <span>{formatDate(note.created_at)}</span>
                  {note.is_evidence && (
                    <span className="flex items-center gap-1 text-green-400">
                      <ShieldCheck className="w-3 h-3" />
                      Evidence
                    </span>
                  )}
                  {note.updated_by && (
                    <span className="italic">edited</span>
                  )}
                </div>

                <div className="flex items-center gap-1">
                  {canModifyNote(note) && (
                    <button
                      onClick={() => toggleEvidence.mutate(note.id)}
                      className={`p-1 text-xs rounded ${
                        note.is_evidence
                          ? "text-green-400 hover:text-green-300"
                          : "text-[hsl(var(--muted-foreground))] hover:text-green-400"
                      }`}
                      title={note.is_evidence ? "Remove evidence mark" : "Mark as evidence"}
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {canModifyNote(note) && (
                    <button
                      onClick={() => {
                        setEditingId(note.id);
                        setEditContent(note.content);
                      }}
                      className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                      title="Edit"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {canDeleteNote(note) && (
                    <button
                      onClick={() => deleteNote.mutate(note.id)}
                      className="p-1 text-[hsl(var(--muted-foreground))] hover:text-red-400"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {editingId === note.id ? (
                <div className="mt-2 flex gap-2">
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={2}
                    className="flex-1 px-2 py-1.5 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
                  />
                  <div className="flex flex-col gap-1">
                    <button
                      onClick={() => updateNote.mutate(note.id)}
                      className="p-1 text-green-400 hover:text-green-300"
                    >
                      <Check className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ) : (
                <p className="mt-2 text-sm whitespace-pre-wrap">{note.content}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
