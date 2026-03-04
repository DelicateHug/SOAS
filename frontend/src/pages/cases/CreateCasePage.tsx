import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TagInput } from "@/components/ui/TagInput";

export function CreateCasePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: 3,
    tags: [] as string[],
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<{ id: string }>("/cases", {
        title: form.title,
        description: form.description || undefined,
        priority: form.priority,
        tags: form.tags,
      }),
    onSuccess: (data) => {
      navigate(`/cases/${data.id}`);
    },
  });

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">New Case</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="space-y-4"
      >
        <div>
          <label className="block text-sm font-medium mb-1">Title *</label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
            required
            placeholder="Case title"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
            rows={4}
            placeholder="Case description..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Priority</label>
          <select
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
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
          <TagInput
            value={form.tags}
            onChange={(tags) => setForm({ ...form, tags })}
            placeholder="Type a tag, press comma to add"
          />
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            disabled={create.isPending || !form.title}
            className="px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50"
          >
            {create.isPending ? "Creating..." : "Create Case"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/cases")}
            className="px-4 py-2 border border-[hsl(var(--border))] rounded-md"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
