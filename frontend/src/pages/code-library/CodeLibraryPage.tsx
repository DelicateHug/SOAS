/**
 * Code Library management page - browse, create, edit, and share custom code blocks.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Star,
  Globe,
  Lock,
  Pencil,
  Trash2,
  Code,
  Shield,
} from "lucide-react";
import {
  useCodeLibraryBlocks,
  useDeleteBlock,
  useToggleFavorite,
  type CodeLibraryBlock,
} from "@/components/graph-editor/hooks/useCodeLibrary";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import { BranchStatusBadge, PendingCreateBadge } from "@/components/ui/BranchStatusBadge";
import { api } from "@/lib/api";
import type { ChangeRequestDetail } from "@/types/api";
import { CodeBlockEditor } from "./CodeBlockEditor";
import { CodeBlockPermissionsDialog } from "./components/CodeBlockPermissionsDialog";
import { AIActionsBar } from "@/components/ai/AIActionsBar";

const languageColors: Record<string, string> = {
  python: "bg-blue-100 text-blue-800",
  javascript: "bg-yellow-100 text-yellow-800",
  bash: "bg-gray-100 text-gray-800",
};

export function CodeLibraryPage() {
  const [search, setSearch] = useState("");
  const [language, setLanguage] = useState("");
  const [page, setPage] = useState(1);
  const [editingBlock, setEditingBlock] = useState<CodeLibraryBlock | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [permissionsBlock, setPermissionsBlock] = useState<CodeLibraryBlock | null>(null);

  const { data, isLoading } = useCodeLibraryBlocks({
    search: search || undefined,
    language: language || undefined,
    page,
    per_page: 25,
  });

  const deleteBlock = useDeleteBlock();
  const toggleFavorite = useToggleFavorite();

  const { isDevMode } = useDeploymentMode();
  const { data: activeCRs } = useQuery({
    queryKey: ["change-requests", "active", "code_library"],
    queryFn: () => api.get<ChangeRequestDetail[]>("/change-requests/active?entity_type=code_library"),
    enabled: isDevMode,
    staleTime: 10_000,
  });

  const crByEntityId = new Map<string, ChangeRequestDetail>();
  const pendingCreates: ChangeRequestDetail[] = [];
  for (const cr of activeCRs ?? []) {
    if (cr.action === "create") pendingCreates.push(cr);
    else if (cr.entity_id && !crByEntityId.has(cr.entity_id)) crByEntityId.set(cr.entity_id, cr);
  }

  const blocks = data?.data || [];
  const meta = data?.meta;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Code className="w-6 h-6" />
          <h1 className="text-2xl font-bold">Code Library</h1>
        </div>
        <button
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 text-sm"
        >
          <Plus className="w-4 h-4" />
          New Block
        </button>
      </div>

      <div className="mb-3">
        <AIActionsBar pageKey="code_library" context={{ language }} />
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search blocks..."
            className="w-full pl-10 pr-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm"
          />
        </div>
        <select
          value={language}
          onChange={(e) => {
            setLanguage(e.target.value);
            setPage(1);
          }}
          className="px-3 py-1.5 border border-[var(--color-border)] rounded-md text-sm bg-[var(--color-bg)]"
        >
          <option value="">All Languages</option>
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="bash">Bash</option>
        </select>
      </div>

      {/* Block list */}
      {isLoading ? (
        <div className="text-center py-12 text-[var(--color-text-muted)]">Loading...</div>
      ) : blocks.length === 0 ? (
        <div className="text-center py-12">
          <Code className="w-12 h-12 mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
          <p className="text-[var(--color-text-muted)]">
            {search ? "No matching blocks found" : "No code blocks yet. Create your first one!"}
          </p>
        </div>
      ) : (
        <div className="grid gap-3">
          {pendingCreates.map((cr) => (
            <div key={cr.id} className="flex items-center gap-4 p-4 border border-green-500/30 rounded-lg bg-green-500/5">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {(cr as unknown as { snapshot?: { name?: string } }).snapshot?.name ?? cr.title}
                  </span>
                  <PendingCreateBadge changeRequest={cr} />
                </div>
              </div>
            </div>
          ))}
          {blocks.map((block) => {
            const cr = crByEntityId.get(block.id);
            const branchStatus = cr?.action === "delete" ? "pending_delete" as const : cr?.action === "update" ? "modified" as const : "unchanged" as const;
            return (
            <div
              key={block.id}
              className={`flex items-center gap-4 p-4 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-2)] transition-colors ${branchStatus === "pending_delete" ? "opacity-50" : ""}`}
            >
              {/* Favorite star */}
              <button
                onClick={() => toggleFavorite.mutate(block.id)}
                className="flex-shrink-0"
                title={block.is_favorited ? "Remove from favorites" : "Add to favorites"}
              >
                <Star
                  className={`w-4 h-4 ${
                    block.is_favorited
                      ? "fill-yellow-400 text-yellow-400"
                      : "text-[var(--color-text-muted)]"
                  }`}
                />
              </button>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium text-sm truncate">{block.name}</h3>
                  {branchStatus !== "unchanged" && cr && <BranchStatusBadge branchStatus={branchStatus} changeRequest={cr} />}
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      languageColors[block.language] || "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {block.language}
                  </span>
                  {block.is_public ? (
                    <span title="Public"><Globe className="w-3 h-3 text-green-500" /></span>
                  ) : (
                    <span title="Private"><Lock className="w-3 h-3 text-[var(--color-text-muted)]" /></span>
                  )}
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    v{block.version}
                  </span>
                </div>
                {block.description && (
                  <p className="text-xs text-[var(--color-text-muted)] truncate">
                    {block.description}
                  </p>
                )}
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                  by {block.created_by.display_name}
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => setPermissionsBlock(block)}
                  className="p-1.5 hover:bg-[var(--color-surface-2)] rounded"
                  title="Permissions"
                >
                  <Shield className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setEditingBlock(block)}
                  className="p-1.5 hover:bg-[var(--color-surface-2)] rounded"
                  title="Edit"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Delete "${block.name}"?`)) {
                      deleteBlock.mutate(block.id);
                    }
                  }}
                  className="p-1.5 hover:bg-red-100 rounded text-red-500"
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
          })}
        </div>
      )}

      {/* Pagination */}
      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-[var(--color-text-muted)]">
            Page {page} of {meta.total_pages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))}
            disabled={page === meta.total_pages}
            className="px-3 py-1 text-sm border rounded disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* Create/Edit dialog */}
      {(isCreating || editingBlock) && (
        <CodeBlockEditor
          block={editingBlock ?? undefined}
          onClose={() => {
            setIsCreating(false);
            setEditingBlock(null);
          }}
        />
      )}

      {/* Permissions dialog */}
      {permissionsBlock && (
        <CodeBlockPermissionsDialog
          blockId={permissionsBlock.id}
          blockName={permissionsBlock.name}
          onClose={() => setPermissionsBlock(null)}
        />
      )}
    </div>
  );
}
