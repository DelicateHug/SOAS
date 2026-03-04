import { useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type { IncidentFile } from "@/types/api";

interface Props {
  incidentId: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FilesTab({ incidentId }: Props) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: files } = useQuery({
    queryKey: ["incident-files", incidentId],
    queryFn: () => api.get<IncidentFile[]>(`/incidents/${incidentId}/files`),
  });

  const uploadFile = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<IncidentFile>(`/incidents/${incidentId}/files`, formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-files", incidentId] });
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const deleteFile = useMutation({
    mutationFn: (fileId: string) =>
      api.delete(`/incidents/${incidentId}/files/${fileId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-files", incidentId] });
    },
  });

  const toggleEvidence = useMutation({
    mutationFn: (fileId: string) =>
      api.post<IncidentFile>(`/incidents/${incidentId}/files/${fileId}/evidence`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident-files", incidentId] });
    },
  });

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    droppedFiles.forEach((file) => uploadFile.mutate(file));
  };

  return (
    <div className="space-y-4">
      <SectionHeader title="Files" />

      {/* Upload zone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-[hsl(var(--border))] rounded-lg p-8 text-center hover:border-[hsl(var(--primary))] transition-colors"
      >
        <p className="text-sm text-[hsl(var(--muted-foreground))] mb-2">
          Drag & drop files here, or
        </p>
        <input
          ref={fileInputRef}
          type="file"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadFile.mutate(file);
          }}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="px-4 py-1.5 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm"
        >
          Choose File
        </button>
        {uploadFile.isPending && (
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2">Uploading...</p>
        )}
      </div>

      {/* File list */}
      <div className="space-y-2">
        {files?.map((file) => (
          <div
            key={file.id}
            className="flex items-center gap-3 rounded-lg border border-[hsl(var(--border))] px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium truncate">{file.filename}</span>
                {file.is_evidence && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 shrink-0">
                    evidence
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-[hsl(var(--muted-foreground))] mt-0.5">
                <span>{formatFileSize(file.file_size)}</span>
                <span>{file.content_type}</span>
                <div className="flex items-center gap-1">
                  <UserAvatar displayName={file.uploaded_by.display_name} size="sm" />
                  <span>{file.uploaded_by.display_name}</span>
                </div>
                <span>{formatDate(file.created_at)}</span>
                {file.expires_at && (
                  <span className={new Date(file.expires_at) < new Date() ? "text-red-400" : ""}>
                    Expires {formatDate(file.expires_at)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-1 shrink-0">
              <a
                href={`/api/v1/incidents/${incidentId}/files/${file.id}/download`}
                className="text-xs px-2 py-1 rounded border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
              >
                Download
              </a>
              <button
                onClick={() => toggleEvidence.mutate(file.id)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  file.is_evidence
                    ? "border-amber-500 text-amber-400"
                    : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-amber-400"
                }`}
              >
                {file.is_evidence ? "Unmark" : "Evidence"}
              </button>
              {file.can_delete && (
                <button
                  onClick={() => {
                    if (confirm("Delete this file?")) deleteFile.mutate(file.id);
                  }}
                  className="text-xs px-2 py-1 rounded border border-[hsl(var(--border))] text-red-400 hover:text-red-300 transition-colors"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
        {(!files || files.length === 0) && (
          <div className="py-8 text-center text-[hsl(var(--muted-foreground))]">
            No files attached yet
          </div>
        )}
      </div>
    </div>
  );
}
