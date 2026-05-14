import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { Plus, Trash2, Edit3, Check, X } from "lucide-react";
import type { IssueChecklistItem } from "@/types/api";

interface Props {
  issueId: string;
  issueCreatorId: string;
}

export function ChecklistTab({ issueId, issueCreatorId }: Props) {
  const { user, hasPermission } = useAuthStore();
  const queryClient = useQueryClient();
  const [newItemContent, setNewItemContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const { data: items, isLoading } = useQuery({
    queryKey: ["issue-checklist", issueId],
    queryFn: () => api.get<IssueChecklistItem[]>(`/issues/${issueId}/checklist`),
  });

  const addItem = useToastMutation({
    mutationFn: () =>
      api.post(`/issues/${issueId}/checklist`, {
        content: newItemContent,
        sort_order: items?.length ?? 0,
      }),
    loadingMessage: "Adding item...",
    successMessage: "Item added.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      setNewItemContent("");
    },
  });

  const toggleItem = useToastMutation({
    mutationFn: (item: IssueChecklistItem) =>
      api.patch(`/issues/${issueId}/checklist/${item.id}`, {
        is_checked: !item.is_checked,
      }),
    loadingMessage: false,
    successMessage: false,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
    },
  });

  const updateItem = useToastMutation({
    mutationFn: (itemId: string) =>
      api.patch(`/issues/${issueId}/checklist/${itemId}`, {
        content: editContent,
      }),
    loadingMessage: "Saving item...",
    successMessage: "Item saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      setEditingId(null);
    },
  });

  const deleteItem = useToastMutation({
    mutationFn: (itemId: string) =>
      api.request(`/issues/${issueId}/checklist/${itemId}`, { method: "DELETE" }),
    loadingMessage: "Deleting item...",
    successMessage: "Item deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issue-checklist", issueId] });
      queryClient.invalidateQueries({ queryKey: ["issue", issueId] });
    },
  });

  const isIssueCreator = user?.id === issueCreatorId;

  const canModifyItem = (item: IssueChecklistItem) =>
    item.created_by.id === user?.id ||
    isIssueCreator ||
    hasPermission("issue:update");

  const canDeleteItem = (item: IssueChecklistItem) =>
    item.created_by.id === user?.id ||
    isIssueCreator ||
    hasPermission("issue:delete");

  const checkedCount = items?.filter((it) => it.is_checked).length ?? 0;
  const totalCount = items?.length ?? 0;

  return (
    <div>
      {/* Progress */}
      {totalCount > 0 && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-[var(--color-text-muted)]">
              {checkedCount}/{totalCount} completed
            </span>
            <span className="text-[var(--color-text-muted)]">
              {totalCount > 0 ? Math.round((checkedCount / totalCount) * 100) : 0}%
            </span>
          </div>
          <div className="w-full h-2 bg-[var(--color-surface-2)] rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 transition-all duration-300"
              style={{ width: `${totalCount > 0 ? (checkedCount / totalCount) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Add item (any user with issue:read can add) */}
      <div className="flex gap-2 mb-4">
        <input
          value={newItemContent}
          onChange={(e) => setNewItemContent(e.target.value)}
          placeholder="Add checklist item..."
          className="flex-1 px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
          onKeyDown={(e) => {
            if (e.key === "Enter" && newItemContent.trim()) {
              addItem.mutate();
            }
          }}
        />
        <button
          onClick={() => addItem.mutate()}
          disabled={!newItemContent.trim() || addItem.isPending}
          className="flex items-center gap-1 px-3 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md disabled:opacity-50 text-sm"
        >
          <Plus className="w-4 h-4" />
          Add
        </button>
      </div>

      {/* Checklist items */}
      {isLoading ? (
        <div className="text-center py-4 text-sm">Loading...</div>
      ) : items?.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)] italic text-center py-4">
          No checklist items yet.
        </p>
      ) : (
        <div className="flex flex-col gap-1">
          {items?.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 p-2 rounded-md hover:bg-[var(--color-surface-2)] group"
            >
              <button
                onClick={() => toggleItem.mutate(item)}
                className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                  item.is_checked
                    ? "bg-green-500 border-green-500 text-white"
                    : "border-[var(--color-border)] hover:border-[var(--color-primary)]"
                }`}
              >
                {item.is_checked && <Check className="w-3 h-3" />}
              </button>

              {editingId === item.id ? (
                <div className="flex-1 flex gap-2">
                  <input
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="flex-1 px-2 py-1 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") updateItem.mutate(item.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    autoFocus
                  />
                  <button
                    onClick={() => updateItem.mutate(item.id)}
                    className="p-1 text-green-400 hover:text-green-300"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <>
                  <span
                    className={`flex-1 text-sm ${
                      item.is_checked ? "line-through text-[var(--color-text-muted)]" : ""
                    }`}
                  >
                    {item.content}
                  </span>
                  <span className="text-xs text-[var(--color-text-muted)] hidden group-hover:block">
                    {item.created_by.display_name}
                  </span>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                    {canModifyItem(item) && (
                      <button
                        onClick={() => {
                          setEditingId(item.id);
                          setEditContent(item.content);
                        }}
                        className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                        title="Edit"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {canDeleteItem(item) && (
                      <button
                        onClick={() => deleteItem.mutate(item.id)}
                        className="p-1 text-[var(--color-text-muted)] hover:text-red-400"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
