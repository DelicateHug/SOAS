/**
 * Issues panel for the graph editor right sidebar.
 * Lists all issues linked to the automation and allows full CRUD
 * without leaving the graph (status, notes, checklist).
 */

import { useState, useRef, useMemo, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { issueStatusColors, issueStatusLabels } from "@/lib/utils";
import {
  Plus,
  ChevronLeft,
  Trash2,
  Square,
  CheckSquare,
  Shield,
  Pencil,
} from "lucide-react";
import type {
  GraphIssueItem,
  IssueDetail,
  IssueNote,
  IssueChecklistItem,
  UserRead,
  IssueStatus,
} from "@/types/api";

const ALL_STATUSES: IssueStatus[] = ["open", "in_progress", "resolved", "closed", "wont_fix"];

interface GraphIssuePanelProps {
  automationId: string;
  issues: GraphIssueItem[];
  onIssuesChanged?: () => void;
  /** When set externally (e.g. double-click annotation), opens that issue */
  focusIssueId?: string | null;
  onFocusConsumed?: () => void;
}

export function GraphIssuePanel({ automationId, issues, onIssuesChanged, focusIssueId, onFocusConsumed }: GraphIssuePanelProps) {
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);

  // Respond to external focus requests
  useEffect(() => {
    if (focusIssueId) {
      setSelectedIssueId(focusIssueId);
      onFocusConsumed?.();
    }
  }, [focusIssueId, onFocusConsumed]);

  if (selectedIssueId) {
    return (
      <IssueDetailView
        issueId={selectedIssueId}
        onBack={() => setSelectedIssueId(null)}
        onIssuesChanged={onIssuesChanged}
      />
    );
  }

  return (
    <IssueListView
      automationId={automationId}
      issues={issues}
      onSelect={setSelectedIssueId}
    />
  );
}

// ---------------------------------------------------------------------------
// Issue List
// ---------------------------------------------------------------------------

function IssueListView({
  automationId,
  issues,
  onSelect,
}: {
  automationId: string;
  issues: GraphIssueItem[];
  onSelect: (id: string) => void;
}) {
  const hasPermission = useAuthStore((s) => s.hasPermission);

  // Also fetch all issues linked to this automation (not just graph-annotated ones)
  const { data: allIssues } = useQuery({
    queryKey: ["issues-by-target", "automation", automationId],
    queryFn: () =>
      api.get<GraphIssueItem[]>(`/issues/by-target/automation/${automationId}`),
  });

  // Merge: graph-annotated issues + any non-annotated linked issues
  const graphIds = new Set(issues.map((i) => i.id));
  const extraIssues = (allIssues ?? []).filter((i) => !graphIds.has(i.id));
  const combined = [...issues, ...extraIssues];

  return (
    <div className="flex flex-col h-full">
      {hasPermission("issue:create") && (
        <div className="p-2 border-b border-[hsl(var(--border))]">
          <a
            href={`/issues/new?linkType=automation&linkId=${automationId}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-[10px] text-[hsl(var(--primary))] hover:underline"
          >
            <Plus className="w-3 h-3" />
            New Issue
          </a>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {combined.length === 0 ? (
          <div className="p-3 text-center text-xs text-[hsl(var(--muted-foreground))]">
            No issues linked to this automation.
          </div>
        ) : (
          combined.map((issue) => (
            <button
              key={issue.id}
              type="button"
              onClick={() => onSelect(issue.id)}
              className="w-full text-left px-2 py-2 border-b border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))] transition-colors"
            >
              <p className="text-xs font-medium truncate">{issue.title}</p>
              <div className="flex items-center gap-1 mt-0.5">
                <span
                  className={`text-[10px] px-1 rounded ${
                    issueStatusColors[issue.status] ?? "bg-gray-500/15 text-gray-400"
                  }`}
                >
                  {issueStatusLabels[issue.status] ?? issue.status}
                </span>
                {issue.assigned_to && (
                  <span className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">
                    {issue.assigned_to.display_name}
                  </span>
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Issue Detail
// ---------------------------------------------------------------------------

type DetailTab = "info" | "notes" | "checklist";

function IssueDetailView({
  issueId,
  onBack,
  onIssuesChanged,
}: {
  issueId: string;
  onBack: () => void;
  onIssuesChanged?: () => void;
}) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const [tab, setTab] = useState<DetailTab>("info");

  const { data: issue } = useQuery({
    queryKey: ["issue", issueId],
    queryFn: () => api.get<IssueDetail>(`/issues/${issueId}`),
  });

  const { data: users } = useQuery({
    queryKey: ["users-brief"],
    queryFn: () => api.get<{ data: UserRead[] }>("/admin/users?per_page=100"),
  });

  const updateIssue = useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      api.patch(`/issues/${issueId}`, fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
      onIssuesChanged?.();
    },
  });

  if (!issue) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-2 border-b border-[hsl(var(--border))]">
          <button onClick={onBack} className="flex items-center gap-1 text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]">
            <ChevronLeft className="w-3 h-3" />
            Back
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Loading...</p>
        </div>
      </div>
    );
  }

  const isCreator = user?.id === issue.created_by.id;
  const canEdit = isCreator || hasPermission("issue:update");

  const tabs: { id: DetailTab; label: string; count?: number }[] = [
    { id: "info", label: "Info" },
    { id: "notes", label: "Notes", count: issue.note_count },
    {
      id: "checklist",
      label: "Tasks",
      count: issue.checklist_total > 0
        ? issue.checklist_checked
        : undefined,
    },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-2 border-b border-[hsl(var(--border))]">
        <button onClick={onBack} className="flex items-center gap-1 text-[10px] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] mb-1">
          <ChevronLeft className="w-3 h-3" />
          All Issues
        </button>
        <p className="text-xs font-semibold truncate">{issue.title}</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[hsl(var(--border))]">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 px-1 py-1.5 text-[10px] font-medium border-b-2 transition-colors ${
              tab === t.id
                ? "border-blue-500 text-[hsl(var(--foreground))]"
                : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
            }`}
          >
            {t.label}
            {t.count != null && (
              <span className="ml-0.5 text-[9px] opacity-60">({t.count})</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === "info" && (
          <InfoTab
            issue={issue}
            users={users?.data ?? []}
            canEdit={canEdit}
            onUpdate={(fields) => updateIssue.mutate(fields)}
          />
        )}
        {tab === "notes" && (
          <NotesTab
            issueId={issueId}
            issueCreatorId={issue.created_by.id}
          />
        )}
        {tab === "checklist" && (
          <ChecklistTab
            issueId={issueId}
            issueCreatorId={issue.created_by.id}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// User Search Select (filterable dropdown)
// ---------------------------------------------------------------------------

function UserSearchSelect({
  users,
  value,
  onChange,
  disabled,
}: {
  users: UserRead[];
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedUser = useMemo(
    () => users.find((u) => u.id === value) ?? null,
    [users, value]
  );

  const filtered = useMemo(
    () =>
      search
        ? users.filter((u) =>
            u.display_name.toLowerCase().includes(search.toLowerCase())
          )
        : users,
    [users, search]
  );

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearch("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (disabled) {
    return (
      <div className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] opacity-50">
        {selectedUser?.display_name ?? "Unassigned"}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text"
        value={isOpen ? search : selectedUser?.display_name ?? ""}
        placeholder="Search users..."
        onFocus={() => {
          setIsOpen(true);
          setSearch("");
        }}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
      />
      {isOpen && (
        <div className="absolute z-50 left-0 right-0 mt-0.5 max-h-40 overflow-y-auto border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg">
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setIsOpen(false);
              setSearch("");
            }}
            className={`w-full text-left px-2 py-1 text-xs hover:bg-[hsl(var(--accent))] ${
              !value ? "bg-[hsl(var(--accent))]" : ""
            }`}
          >
            Unassigned
          </button>
          {filtered.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => {
                onChange(u.id);
                setIsOpen(false);
                setSearch("");
              }}
              className={`w-full text-left px-2 py-1 text-xs hover:bg-[hsl(var(--accent))] ${
                u.id === value ? "bg-[hsl(var(--accent))]" : ""
              }`}
            >
              {u.display_name}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-2 py-1 text-xs text-[hsl(var(--muted-foreground))]">
              No matches
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Info Tab
// ---------------------------------------------------------------------------

function InfoTab({
  issue,
  users,
  canEdit,
  onUpdate,
}: {
  issue: IssueDetail;
  users: UserRead[];
  canEdit: boolean;
  onUpdate: (fields: Record<string, unknown>) => void;
}) {
  return (
    <div className="p-2 space-y-3">
      {/* Status */}
      <div>
        <label className="block text-[10px] font-medium text-[hsl(var(--muted-foreground))] uppercase mb-0.5">
          Status
        </label>
        <select
          value={issue.status}
          onChange={(e) => onUpdate({ status: e.target.value })}
          disabled={!canEdit}
          className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] disabled:opacity-50"
        >
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {issueStatusLabels[s]}
            </option>
          ))}
        </select>
      </div>

      {/* Assigned To */}
      <div>
        <label className="block text-[10px] font-medium text-[hsl(var(--muted-foreground))] uppercase mb-0.5">
          Assigned To
        </label>
        <UserSearchSelect
          users={users}
          value={issue.assigned_to?.id ?? null}
          onChange={(id) => onUpdate({ assigned_to: id })}
          disabled={!canEdit}
        />
      </div>

      {/* Description */}
      {issue.description && (
        <div>
          <label className="block text-[10px] font-medium text-[hsl(var(--muted-foreground))] uppercase mb-0.5">
            Description
          </label>
          <p className="text-xs text-[hsl(var(--foreground))] whitespace-pre-wrap">
            {issue.description}
          </p>
        </div>
      )}

      {/* Meta */}
      <div className="text-[10px] text-[hsl(var(--muted-foreground))] space-y-0.5">
        <p>Created by {issue.created_by.display_name}</p>
        <p>{new Date(issue.created_at).toLocaleString()}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Notes Tab
// ---------------------------------------------------------------------------

function NotesTab({
  issueId,
  issueCreatorId,
}: {
  issueId: string;
  issueCreatorId: string;
}) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const [newNote, setNewNote] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: notes } = useQuery({
    queryKey: ["issue-notes", issueId],
    queryFn: () => api.get<IssueNote[]>(`/issues/${issueId}/notes`),
  });

  const addNote = useMutation({
    mutationFn: () => api.post(`/issues/${issueId}/notes`, { content: newNote }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
      setNewNote("");
    },
  });

  const updateNote = useMutation({
    mutationFn: (noteId: string) =>
      api.patch(`/issues/${issueId}/notes/${noteId}`, { content: editContent }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
      setEditingId(null);
    },
  });

  const deleteNote = useMutation({
    mutationFn: (noteId: string) =>
      api.request(`/issues/${issueId}/notes/${noteId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
    },
  });

  const toggleEvidence = useMutation({
    mutationFn: (noteId: string) =>
      api.post(`/issues/${issueId}/notes/${noteId}/evidence`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-notes", issueId] });
    },
  });

  const canModify = (note: IssueNote) =>
    note.created_by.id === user?.id ||
    user?.id === issueCreatorId ||
    hasPermission("issue:update");

  return (
    <div className="flex flex-col h-full">
      {/* Add note */}
      {hasPermission("issue:create") && (
        <form
          className="p-2 border-b border-[hsl(var(--border))]"
          onSubmit={(e) => {
            e.preventDefault();
            if (newNote.trim()) addNote.mutate();
          }}
        >
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Add a note..."
            rows={2}
            className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] resize-none"
          />
          <button
            type="submit"
            disabled={!newNote.trim() || addNote.isPending}
            className="mt-1 px-2 py-0.5 text-[10px] bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded disabled:opacity-50"
          >
            Add
          </button>
        </form>
      )}

      {/* Notes list */}
      <div className="flex-1 overflow-y-auto">
        {(notes ?? []).length === 0 ? (
          <p className="p-3 text-center text-xs text-[hsl(var(--muted-foreground))]">
            No notes yet.
          </p>
        ) : (
          (notes ?? []).map((note) => (
            <div
              key={note.id}
              className={`p-2 border-b border-[hsl(var(--border))] text-xs ${
                note.is_evidence ? "bg-green-500/5 border-l-2 border-l-green-500" : ""
              }`}
            >
              {editingId === note.id ? (
                <div>
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={2}
                    className="w-full px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] resize-none"
                    autoFocus
                  />
                  <div className="flex gap-1 mt-1">
                    <button
                      onClick={() => updateNote.mutate(note.id)}
                      className="px-1.5 py-0.5 text-[10px] bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="px-1.5 py-0.5 text-[10px] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="whitespace-pre-wrap break-words">{note.content}</p>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                      {note.created_by.display_name}
                    </span>
                    {canModify(note) && (
                      <div className="flex items-center gap-0.5">
                        <button
                          onClick={() => toggleEvidence.mutate(note.id)}
                          title={note.is_evidence ? "Remove evidence mark" : "Mark as evidence"}
                          className="p-0.5 hover:bg-[hsl(var(--accent))] rounded"
                        >
                          <Shield className={`w-3 h-3 ${note.is_evidence ? "text-green-400" : "text-[hsl(var(--muted-foreground))]"}`} />
                        </button>
                        <button
                          onClick={() => {
                            setEditingId(note.id);
                            setEditContent(note.content);
                          }}
                          className="p-0.5 hover:bg-[hsl(var(--accent))] rounded"
                        >
                          <Pencil className="w-3 h-3 text-[hsl(var(--muted-foreground))]" />
                        </button>
                        <button
                          onClick={() => deleteNote.mutate(note.id)}
                          className="p-0.5 hover:bg-[hsl(var(--accent))] rounded"
                        >
                          <Trash2 className="w-3 h-3 text-red-400" />
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Checklist Tab
// ---------------------------------------------------------------------------

function ChecklistTab({
  issueId,
  issueCreatorId,
}: {
  issueId: string;
  issueCreatorId: string;
}) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const [newItem, setNewItem] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: items } = useQuery({
    queryKey: ["issue-checklist", issueId],
    queryFn: () => api.get<IssueChecklistItem[]>(`/issues/${issueId}/checklist`),
  });

  const addItem = useMutation({
    mutationFn: () =>
      api.post(`/issues/${issueId}/checklist`, {
        content: newItem,
        sort_order: items?.length ?? 0,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
      setNewItem("");
    },
  });

  const toggleItem = useMutation({
    mutationFn: (item: IssueChecklistItem) =>
      api.patch(`/issues/${issueId}/checklist/${item.id}`, {
        is_checked: !item.is_checked,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
    },
  });

  const updateItem = useMutation({
    mutationFn: (itemId: string) =>
      api.patch(`/issues/${issueId}/checklist/${itemId}`, { content: editContent }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      setEditingId(null);
    },
  });

  const deleteItem = useMutation({
    mutationFn: (itemId: string) =>
      api.request(`/issues/${issueId}/checklist/${itemId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
    },
  });

  const canModify = (item: IssueChecklistItem) =>
    item.created_by.id === user?.id ||
    user?.id === issueCreatorId ||
    hasPermission("issue:update");

  const checked = items?.filter((i) => i.is_checked).length ?? 0;
  const total = items?.length ?? 0;

  return (
    <div className="flex flex-col h-full">
      {/* Progress */}
      {total > 0 && (
        <div className="px-2 pt-2">
          <div className="flex items-center justify-between text-[10px] text-[hsl(var(--muted-foreground))] mb-1">
            <span>{checked}/{total}</span>
            <span>{Math.round((checked / total) * 100)}%</span>
          </div>
          <div className="h-1 bg-[hsl(var(--accent))] rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all"
              style={{ width: `${(checked / total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Add item */}
      {hasPermission("issue:create") && (
        <form
          className="p-2 border-b border-[hsl(var(--border))]"
          onSubmit={(e) => {
            e.preventDefault();
            if (newItem.trim()) addItem.mutate();
          }}
        >
          <div className="flex gap-1">
            <input
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              placeholder="Add task..."
              className="flex-1 px-2 py-1 text-xs border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
            />
            <button
              type="submit"
              disabled={!newItem.trim() || addItem.isPending}
              className="px-1.5 py-1 text-[hsl(var(--primary))] disabled:opacity-50"
            >
              <Plus className="w-3 h-3" />
            </button>
          </div>
        </form>
      )}

      {/* Items list */}
      <div className="flex-1 overflow-y-auto">
        {(items ?? []).length === 0 ? (
          <p className="p-3 text-center text-xs text-[hsl(var(--muted-foreground))]">
            No tasks yet.
          </p>
        ) : (
          (items ?? []).map((item) => (
            <div
              key={item.id}
              className="flex items-start gap-1.5 px-2 py-1.5 border-b border-[hsl(var(--border))] group"
            >
              <button
                onClick={() => toggleItem.mutate(item)}
                className="mt-0.5 shrink-0"
              >
                {item.is_checked ? (
                  <CheckSquare className="w-3.5 h-3.5 text-green-400" />
                ) : (
                  <Square className="w-3.5 h-3.5 text-[hsl(var(--muted-foreground))]" />
                )}
              </button>

              {editingId === item.id ? (
                <div className="flex-1">
                  <input
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full px-1 py-0.5 text-xs border border-[hsl(var(--input))] rounded bg-[hsl(var(--background))]"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") updateItem.mutate(item.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                  />
                </div>
              ) : (
                <span
                  className={`flex-1 text-xs ${
                    item.is_checked
                      ? "line-through text-[hsl(var(--muted-foreground))]"
                      : ""
                  }`}
                >
                  {item.content}
                </span>
              )}

              {canModify(item) && editingId !== item.id && (
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 shrink-0">
                  <button
                    onClick={() => {
                      setEditingId(item.id);
                      setEditContent(item.content);
                    }}
                    className="p-0.5 hover:bg-[hsl(var(--accent))] rounded"
                  >
                    <Pencil className="w-2.5 h-2.5 text-[hsl(var(--muted-foreground))]" />
                  </button>
                  <button
                    onClick={() => deleteItem.mutate(item.id)}
                    className="p-0.5 hover:bg-[hsl(var(--accent))] rounded"
                  >
                    <Trash2 className="w-2.5 h-2.5 text-red-400" />
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
