import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { TagInput } from "@/components/ui/TagInput";
import type { IncidentSeverity } from "@/types/api";

export function CreateIncidentPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    summary: "",
    severity: "medium" as IncidentSeverity,
    source: "",
    tags: [] as string[],
  });

  const create = useToastMutation({
    mutationFn: () =>
      api.post<{ id: string }>("/incidents", {
        title: form.title,
        summary: form.summary || undefined,
        severity: form.severity,
        source: form.source || undefined,
        tags: form.tags,
      }),
    loadingMessage: "Creating incident...",
    successMessage: "Incident created.",
    onSuccess: (data: { id: string }) => {
      navigate(`/incidents/${data.id}`);
    },
  });

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">New Incident</h1>

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
            placeholder="Brief description of the incident"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Summary</label>
          <textarea
            value={form.summary}
            onChange={(e) => setForm({ ...form, summary: e.target.value })}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
            rows={4}
            placeholder="Detailed description..."
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Severity</label>
            <select
              value={form.severity}
              onChange={(e) => setForm({ ...form, severity: e.target.value as IncidentSeverity })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
            >
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="informational">Informational</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Source</label>
            <input
              type="text"
              value={form.source}
              onChange={(e) => setForm({ ...form, source: e.target.value })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
              placeholder="e.g., SIEM, Manual, EDR"
            />
          </div>
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
            {create.isPending ? "Creating..." : "Create Incident"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/incidents")}
            className="px-4 py-2 border border-[hsl(var(--border))] rounded-md"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
