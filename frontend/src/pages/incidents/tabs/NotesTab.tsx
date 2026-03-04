import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { IncidentNote } from "@/types/api";

interface Props {
  incidentId: string;
}

export function NotesTab({ incidentId }: Props) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: notes } = useQuery({
    queryKey: ["incident-notes", incidentId],
    queryFn: () => api.get<IncidentNote[]>(`/incidents/${incidentId}/notes`),
  });

  const createNote = useMutation({
    mutationFn: (content: string) =>
      api.post(`/incidents/${incidentId}/notes`, { content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", incidentId] });
      setNewNote("");
      setShowForm(false);
    },
  });

  const updateNote = useMutation({
    mutationFn: ({ noteId, content }: { noteId: string; content: string }) =>
      api.patch(`/incidents/${incidentId}/notes/${noteId}`, { content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", incidentId] });
      setEditingId(null);
    },
  });

  const deleteNote = useMutation({
    mutationFn: (noteId: string) =>
      api.delete(`/incidents/${incidentId}/notes/${noteId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", incidentId] });
    },
  });

  const toggleEvidence = useMutation({
    mutationFn: (noteId: string) =>
      api.post<IncidentNote>(`/incidents/${incidentId}/notes/${noteId}/evidence`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-notes", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incident-timeline", incidentId] });
    },
  });

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Notes"
        action={
          !showForm ? (
            <button
              onClick={() => setShowForm(true)}
              className="px-3 py-1.5 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-xs font-medium"
            >
              Add Note
            </button>
          ) : undefined
        }
      />

      {/* New note form */}
      {showForm && (
        <div className="rounded-lg border border-[hsl(var(--border))] p-4">
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Write your note..."
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm min-h-24 resize-y bg-transparent"
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => newNote.trim() && createNote.mutate(newNote.trim())}
              disabled={!newNote.trim() || createNote.isPending}
              className="px-4 py-1.5 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={() => { setShowForm(false); setNewNote(""); }}
              className="px-4 py-1.5 border border-[hsl(var(--border))] rounded-md text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Notes list */}
      <div className="space-y-3">
        {notes?.map((note) => (
          <div key={note.id} className="rounded-lg border border-[hsl(var(--border))] p-4">
            {editingId === note.id ? (
              <div>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm min-h-20 resize-y bg-transparent"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() =>
                      editContent.trim() &&
                      updateNote.mutate({ noteId: note.id, content: editContent.trim() })
                    }
                    className="px-3 py-1 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded text-sm"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="px-3 py-1 border border-[hsl(var(--border))] rounded text-sm"
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
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">
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
                          : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-amber-400"
                      }`}
                    >
                      {note.is_evidence ? "Unmark" : "Evidence"}
                    </button>
                    <button
                      onClick={() => { setEditingId(note.id); setEditContent(note.content); }}
                      className="text-xs px-2 py-0.5 rounded border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => { if (confirm("Delete this note?")) deleteNote.mutate(note.id); }}
                      className="text-xs px-2 py-0.5 rounded border border-[hsl(var(--border))] text-red-400 hover:text-red-300"
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
          <div className="py-8 text-center text-[hsl(var(--muted-foreground))]">
            No notes yet
          </div>
        )}
      </div>
    </div>
  );
}
