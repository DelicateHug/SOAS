import { useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { WriteGuard } from "@/components/work/WriteGuard";
import type { CaseFile } from "@/types/api";

interface Props {
  caseId: string;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FilesTab({ caseId }: Props) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: files } = useQuery({
    queryKey: ["case-files", caseId],
    queryFn: () => api.get<CaseFile[]>(`/cases/${caseId}/files`),
  });

  const uploadFile = useToastMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api.upload<CaseFile>(`/cases/${caseId}/files`, formData);
    },
    loadingMessage: "Uploading file...",
    successMessage: "File uploaded.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-files", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const deleteFile = useToastMutation({
    mutationFn: (fileId: string) =>
      api.delete(`/cases/${caseId}/files/${fileId}`),
    loadingMessage: "Deleting file...",
    successMessage: "File deleted.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-files", caseId] });
    },
  });

  const toggleEvidence = useToastMutation({
    mutationFn: (fileId: string) =>
      api.post<CaseFile>(`/cases/${caseId}/files/${fileId}/evidence`),
    loadingMessage: "Updating evidence...",
    successMessage: "Evidence updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case-files", caseId] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", caseId] });
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
      <WriteGuard blockedTitle="Start work on this group to upload files">
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          className="border-2 border-dashed border-[var(--color-border)] rounded-lg p-8 text-center hover:border-[var(--color-primary)] transition-colors"
        >
          <p className="text-sm text-[var(--color-text-muted)] mb-2">
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
            className="px-4 py-1.5 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm"
          >
            Choose File
          </button>
          {uploadFile.isPending && (
            <p className="text-xs text-[var(--color-text-muted)] mt-2">Uploading...</p>
          )}
        </div>
      </WriteGuard>

      {/* File list */}
      <div className="space-y-2">
        {files?.map((file) => (
          <div
            key={file.id}
            className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] px-4 py-3"
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
              <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)] mt-0.5">
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
                href={`/api/v1/cases/${caseId}/files/${file.id}/download`}
                className="text-xs px-2 py-1 rounded border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                Download
              </a>
              <button
                onClick={() => toggleEvidence.mutate(file.id)}
                className={`text-xs px-2 py-1 rounded border transition-colors ${
                  file.is_evidence
                    ? "border-amber-500 text-amber-400"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-amber-400"
                }`}
              >
                {file.is_evidence ? "Unmark" : "Evidence"}
              </button>
              {file.can_delete && (
                <button
                  onClick={() => {
                    if (confirm("Delete this file?")) deleteFile.mutate(file.id);
                  }}
                  className="text-xs px-2 py-1 rounded border border-[var(--color-border)] text-red-400 hover:text-red-300 transition-colors"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
        {(!files || files.length === 0) && (
          <div className="py-8 text-center text-[var(--color-text-muted)]">
            No files attached yet
          </div>
        )}
      </div>
    </div>
  );
}
