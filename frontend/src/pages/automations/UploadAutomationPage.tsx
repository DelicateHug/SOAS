import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import { api } from "@/lib/api";
import { useTeamStore } from "@/stores/teamStore";
import { Upload, ArrowLeft } from "lucide-react";

export function UploadAutomationPage() {
  const { isProduction } = useDeploymentMode();

  if (isProduction) {
    return (
      <div className="max-w-2xl py-12 text-center">
        <h1 className="text-2xl font-bold mb-4">Upload Automation</h1>
        <p className="text-[hsl(var(--muted-foreground))]">
          Editing is disabled in production mode. Switch to dev mode to make changes.
        </p>
      </div>
    );
  }
  const navigate = useNavigate();
  const activeTeamId = useTeamStore((s) => s.activeTeamId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState(300);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");

  const uploadMutation = useToastMutation({
    mutationFn: async () => {
      if (!file) throw new Error("No file selected");

      // Read the .vpy file as JSON
      const text = await file.text();
      let graphData;
      try {
        graphData = JSON.parse(text);
      } catch {
        throw new Error("Invalid .vpy file: must be valid JSON");
      }

      return api.post<{ id: string }>("/automations", {
        name,
        description: description || undefined,
        graph_data: graphData,
        timeout_seconds: timeoutSeconds,
        status: "draft",
        team_id: activeTeamId ?? undefined,
      });
    },
    loadingMessage: "Uploading automation...",
    successMessage: "Automation uploaded.",
    onSuccess: (data) => {
      navigate(`/automations/${data.id}`);
    },
    onError: (err: Error & { detail?: string }) => {
      setError(err.detail || err.message || "Upload failed");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim()) { setError("Name is required"); return; }
    if (!file) { setError("Please select a .vpy file"); return; }

    uploadMutation.mutate();
  };

  return (
    <div className="max-w-2xl">
      <button
        onClick={() => navigate("/automations")}
        className="flex items-center gap-1 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] mb-4"
      >
        <ArrowLeft className="w-4 h-4" /> Back to automations
      </button>

      <h1 className="text-2xl font-bold mb-6">Upload Automation</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Name *</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
            placeholder="My Automation"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
            rows={3}
            placeholder="What does this automation do?"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Timeout (seconds)</label>
          <input
            type="number"
            value={timeoutSeconds}
            onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
            min={10}
            max={3600}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">VisualPython File (.vpy) *</label>
          <div className="border-2 border-dashed border-[hsl(var(--border))] rounded-lg p-6 text-center">
            <input
              type="file"
              accept=".vpy,.json"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
              id="vpy-upload"
            />
            <label
              htmlFor="vpy-upload"
              className="cursor-pointer flex flex-col items-center gap-2"
            >
              <Upload className="w-8 h-8 text-[hsl(var(--muted-foreground))]" />
              {file ? (
                <span className="text-sm font-medium">{file.name}</span>
              ) : (
                <>
                  <span className="text-sm font-medium">Click to select a .vpy file</span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">
                    VisualPython project files (.vpy) or JSON
                  </span>
                </>
              )}
            </label>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={uploadMutation.isPending}
            className="px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50"
          >
            {uploadMutation.isPending ? "Uploading..." : "Upload & Create"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/automations")}
            className="px-4 py-2 border border-[hsl(var(--border))] rounded-md"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
