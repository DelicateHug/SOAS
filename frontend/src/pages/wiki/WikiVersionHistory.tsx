import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { DocumentationViewer } from "@/components/DocumentationViewer";
import { ArrowLeft, RotateCcw, Eye, X } from "lucide-react";
import type { WikiPage, WikiPageVersion } from "@/types/api";

export function WikiVersionHistory() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = useAuthStore();
  const [previewVersion, setPreviewVersion] = useState<WikiPageVersion | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);

  // Get current page
  const { data: page } = useQuery({
    queryKey: ["wiki-page", slug],
    queryFn: () => api.get<WikiPage>(`/wiki/by-slug/${slug}`),
    enabled: !!slug,
  });

  // Get versions
  const { data: versions, isLoading } = useQuery({
    queryKey: ["wiki-versions", page?.id],
    queryFn: () => api.get<WikiPageVersion[]>(`/wiki/${page!.id}/versions`),
    enabled: !!page?.id,
  });

  const handleRestore = async (versionNumber: number) => {
    if (!page) return;
    if (!confirm(`Restore to version ${versionNumber}? This will create a new version with the restored content.`)) return;

    setIsRestoring(true);
    try {
      await api.post(`/wiki/${page.id}/versions/${versionNumber}/restore`);
      queryClient.invalidateQueries({ queryKey: ["wiki-page", slug] });
      queryClient.invalidateQueries({ queryKey: ["wiki-versions", page.id] });
      queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
      navigate(`/wiki/${slug}`);
    } catch (err) {
      console.error("Failed to restore version:", err);
    } finally {
      setIsRestoring(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate(`/wiki/${slug}`)}
          className="p-1.5 rounded-md hover:bg-[hsl(var(--accent))]"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">Version History</h1>
          {page && (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              <Link to={`/wiki/${slug}`} className="hover:underline">{page.title}</Link>
              {" "}&mdash; Current version: v{page.version}
            </p>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : !versions || versions.length === 0 ? (
        <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
          No version history available.
        </div>
      ) : (
        <div className="flex gap-6">
          {/* Version list */}
          <div className={`${previewVersion ? "w-80 shrink-0" : "flex-1"} space-y-2`}>
            {versions.map((v) => (
              <div
                key={v.id}
                className={`border rounded-lg p-4 transition-colors ${
                  previewVersion?.id === v.id
                    ? "border-[hsl(var(--primary))] bg-[hsl(var(--accent))]"
                    : "border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                }`}
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-sm">
                    Version {v.version_number}
                    {page && v.version_number === page.version && (
                      <span className="ml-2 text-xs px-1.5 py-0.5 bg-green-500/15 text-green-400 rounded">
                        Current
                      </span>
                    )}
                  </h3>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setPreviewVersion(previewVersion?.id === v.id ? null : v)}
                      className="p-1 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
                      title="Preview"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    {hasPermission("wiki:update") && page && v.version_number !== page.version && (
                      <button
                        onClick={() => handleRestore(v.version_number)}
                        disabled={isRestoring}
                        className="p-1 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] disabled:opacity-50"
                        title="Restore this version"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
                <div className="text-xs text-[hsl(var(--muted-foreground))] mt-1 space-y-0.5">
                  <p>By {v.created_by.display_name} &middot; {formatDate(v.created_at)}</p>
                  {v.title && <p>Title: {v.title}</p>}
                  {v.change_summary && (
                    <p className="italic">{v.change_summary}</p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Preview panel */}
          {previewVersion && (
            <div className="flex-1 border border-[hsl(var(--border))] rounded-lg">
              <div className="flex items-center justify-between p-4 border-b border-[hsl(var(--border))]">
                <h3 className="font-medium">
                  Preview: Version {previewVersion.version_number}
                </h3>
                <button
                  onClick={() => setPreviewVersion(null)}
                  className="p-1 rounded hover:bg-[hsl(var(--accent))]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="p-6">
                {previewVersion.content ? (
                  <DocumentationViewer content={previewVersion.content} />
                ) : (
                  <p className="text-center py-8 text-[hsl(var(--muted-foreground))]">
                    No content in this version.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
