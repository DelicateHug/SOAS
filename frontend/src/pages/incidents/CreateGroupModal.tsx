import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { X } from "lucide-react";

interface CreateGroupModalProps {
  onClose: () => void;
}

export function CreateGroupModal({ onClose }: CreateGroupModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: 3,
    tags: "",
  });

  const create = useToastMutation({
    mutationFn: () =>
      api.post<{ id: string }>("/cases", {
        title: form.title,
        description: form.description || null,
        priority: form.priority,
        tags: form.tags
          ? form.tags.split(",").map((t) => t.trim()).filter(Boolean)
          : [],
      }),
    loadingMessage: "Creating group...",
    successMessage: "Group created.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-groups"] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--background))] border border-[hsl(var(--border))] rounded-lg shadow-lg w-full max-w-md">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
          <h2 className="font-semibold">Create Incident Group</h2>
          <button
            onClick={onClose}
            className="p-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="p-4 flex flex-col gap-4"
        >
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Group title..."
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Describe this group..."
              rows={3}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] resize-y text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Priority</label>
            <select
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value={1}>P1 - Critical</option>
              <option value={2}>P2 - High</option>
              <option value={3}>P3 - Medium</option>
              <option value={4}>P4 - Low</option>
              <option value={5}>P5 - Minimal</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Tags</label>
            <input
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              placeholder="tag1, tag2, ..."
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={create.isPending || !form.title.trim()}
              className="px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50 text-sm"
            >
              {create.isPending ? "Creating..." : "Create Group"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))] text-sm"
            >
              Cancel
            </button>
          </div>

          {create.isError && (
            <p className="text-sm text-red-400">
              Failed to create group. Please try again.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
