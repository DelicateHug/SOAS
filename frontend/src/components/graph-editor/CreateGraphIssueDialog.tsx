/**
 * Dialog for creating an issue with a graph annotation from the graph editor.
 */

import { useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface CreateGraphIssueDialogProps {
  isOpen: boolean;
  onClose: () => void;
  automationId: string;
  automationVersion: number;
  /** Default annotation position from where the user clicked/placed */
  defaultX: number;
  defaultY: number;
  /** Called after issue is created so collaborators can be notified */
  onCreated?: () => void;
}

export function CreateGraphIssueDialog({
  isOpen,
  onClose,
  automationId,
  automationVersion,
  defaultX,
  defaultY,
  onCreated,
}: CreateGraphIssueDialogProps) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.post("/issues", {
        title,
        description: description || null,
        graph_annotation: {
          x: defaultX,
          y: defaultY,
          width: 200,
          height: 80,
          automation_version: automationVersion,
        },
        links: [
          {
            target_type: "automation",
            target_id: automationId,
          },
        ],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["automation-graph-issues", automationId],
      });
      setTitle("");
      setDescription("");
      onCreated?.();
      onClose();
    },
  });

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-bg)] rounded-lg shadow-lg max-w-md w-full mx-4 border border-[var(--color-border)]">
        <div className="p-4 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Create Graph Issue</h2>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            This issue will be annotated on the graph at version {automationVersion}.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="p-4 flex flex-col gap-3"
        >
          <div>
            <label className="block text-xs font-medium mb-1">Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Issue title..."
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm"
              required
              autoFocus
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the issue..."
              rows={3}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-bg)] text-sm resize-y"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim() || create.isPending}
              className="px-3 py-1.5 text-sm bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 disabled:opacity-50"
            >
              {create.isPending ? "Creating..." : "Create Issue"}
            </button>
          </div>

          {create.isError && (
            <p className="text-xs text-red-400">Failed to create issue.</p>
          )}
        </form>
      </div>
    </div>,
    document.body
  );
}
