import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { CollaborativeMarkdownEditor } from "@/components/wiki/CollaborativeMarkdownEditor";
import { useWikiCollaboration } from "@/components/wiki/useWikiCollaboration";
import { useAuthStore } from "@/stores/authStore";
import { useEntityDraft } from "@/hooks/useEntityDraft";
import { useDraftSave } from "@/hooks/useDraftSave";
import { TagInput } from "@/components/ui/TagInput";
import { TierSelector } from "@/components/ui/TierSelector";
import { useEntityVersion } from "@/hooks/useEntityVersion";
import { Save, ArrowLeft, Send, GitBranch, GitMerge } from "lucide-react";
import type { WikiPage, WikiTreeNode, PushToDevResult } from "@/types/api";

interface NodeCatalogEntry {
  type: string;
  name: string;
  category: string;
}

// Deterministic colour for current user (matches backend)
const COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b",
  "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
];

function getUserColor(userId: string): string {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = ((hash << 5) - hash + userId.charCodeAt(i)) | 0;
  }
  return COLORS[Math.abs(hash) % COLORS.length]!;
}

export function WikiPageEditor() {
  const { slug } = useParams<{ slug?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isEdit = !!slug;

  const [title, setTitle] = useState("");
  const [pageSlug, setPageSlug] = useState("");
  const [content, setContent] = useState("");
  const [parentId, setParentId] = useState<string>("");
  const [tags, setTags] = useState<string[]>([]);
  const [status, setStatus] = useState("published");
  const [icon, setIcon] = useState("");
  const [linkedNodeType, setLinkedNodeType] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Load existing page for editing
  const { data: page, isLoading } = useQuery({
    queryKey: ["wiki-page", slug],
    queryFn: () => api.get<WikiPage>(`/wiki/by-slug/${slug}`),
    enabled: isEdit,
  });

  // Collaboration: only enabled when editing an existing page
  const collaboration = useWikiCollaboration(isEdit ? page?.id : undefined);

  // Draft system: route saves through change requests when in prod mode
  const { draft: activeDraft, hasDraft } = useEntityDraft("wiki_page", page?.id);
  const draftSave = useDraftSave({
    entityType: "wiki_page",
    entityId: page?.id ?? null,
    getTitle: (snapshot) =>
      `${isEdit ? "Update" : "Create"} wiki page: ${snapshot.title || title}`,
    getDiffSummary: (snapshot) => {
      if (!page) return null;
      const diff: Record<string, { old: unknown; new: unknown }> = {};
      if (snapshot.title !== page.title) diff.title = { old: page.title, new: snapshot.title };
      if (snapshot.content !== page.content) diff.content = { old: "(previous content)", new: "(updated content)" };
      if (JSON.stringify(snapshot.tags) !== JSON.stringify(page.tags)) diff.tags = { old: page.tags, new: snapshot.tags };
      if (snapshot.status !== page.status) diff.status = { old: page.status, new: snapshot.status };
      return Object.keys(diff).length > 0 ? diff : null;
    },
  });

  // Branch versioning: view entity at different tiers
  const entityVersion = useEntityVersion("wiki_page", page?.id, isEdit);

  const [isPushingToDev, setIsPushingToDev] = useState(false);
  const handlePushToDev = async () => {
    if (!activeDraft) return;
    setIsPushingToDev(true);
    try {
      const result = await api.post<PushToDevResult>(
        `/change-requests/${activeDraft.id}/push-to-dev`,
      );
      if (result.status === "conflict") {
        alert(`Merge conflict on: ${result.conflicts.join(", ")}`);
      }
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["entity-version"] });
    } catch (err) {
      console.error("Push to dev failed:", err);
    } finally {
      setIsPushingToDev(false);
    }
  };

  // Handle remote field updates from collaborators
  useEffect(() => {
    collaboration.onFieldUpdate.current = (field: string, value: unknown) => {
      switch (field) {
        case "title":
          setTitle(value as string);
          break;
        case "tags":
          setTags(value as string[]);
          break;
        case "status":
          setStatus(value as string);
          break;
        case "icon":
          setIcon(value as string);
          break;
        case "parentId":
          setParentId(value as string);
          break;
        case "linkedNodeType":
          setLinkedNodeType(value as string);
          break;
      }
    };
    return () => {
      collaboration.onFieldUpdate.current = null;
    };
  }, [collaboration.onFieldUpdate]);

  // Load tree for parent selector
  const { data: tree } = useQuery({
    queryKey: ["wiki-tree"],
    queryFn: () => api.get<WikiTreeNode[]>("/wiki/tree"),
  });

  // Load node catalog for linked node type selector
  const { data: nodeCatalog } = useQuery({
    queryKey: ["node-catalog"],
    queryFn: () =>
      api.get<{ nodes: NodeCatalogEntry[] }>("/graph-editor/node-catalog"),
  });

  // Populate form when page loads — prefer draft snapshot over live data
  useEffect(() => {
    if (page) {
      const snap = activeDraft?.snapshot as Record<string, unknown> | undefined;
      setTitle((snap?.title as string) ?? page.title);
      setPageSlug((snap?.slug as string) ?? page.slug);
      setContent((snap?.content as string) ?? page.content ?? "");
      setParentId((snap?.parent_id as string) ?? page.parent_id ?? "");
      setTags((snap?.tags as string[]) ?? page.tags);
      setStatus((snap?.status as string) ?? page.status);
      setIcon((snap?.icon as string) ?? page.icon ?? "");
      setLinkedNodeType((snap?.linked_node_type as string) ?? page.linked_node_type ?? "");
    }
  }, [page, activeDraft]);

  // Flatten tree for parent selector
  function flattenTree(nodes: WikiTreeNode[], depth = 0): Array<{ id: string; title: string; depth: number }> {
    const items: Array<{ id: string; title: string; depth: number }> = [];
    for (const node of nodes) {
      if (page && node.id === page.id) continue;
      items.push({ id: node.id, title: node.title, depth });
      items.push(...flattenTree(node.children, depth + 1));
    }
    return items;
  }

  const parentOptions = tree ? flattenTree(tree) : [];

  // Broadcast field changes to collaborators
  const handleTitleChange = useCallback((value: string) => {
    setTitle(value);
    if (isEdit) collaboration.broadcastFieldUpdate("title", value);
  }, [isEdit, collaboration]);

  const handleTagsChange = useCallback((value: string[]) => {
    setTags(value);
    if (isEdit) collaboration.broadcastFieldUpdate("tags", value);
  }, [isEdit, collaboration]);

  const handleStatusChange = useCallback((value: string) => {
    setStatus(value);
    if (isEdit) collaboration.broadcastFieldUpdate("status", value);
  }, [isEdit, collaboration]);

  const handleIconChange = useCallback((value: string) => {
    setIcon(value);
    if (isEdit) collaboration.broadcastFieldUpdate("icon", value);
  }, [isEdit, collaboration]);

  const handleParentChange = useCallback((value: string) => {
    setParentId(value);
    if (isEdit) collaboration.broadcastFieldUpdate("parentId", value);
  }, [isEdit, collaboration]);

  const handleLinkedNodeChange = useCallback((value: string) => {
    setLinkedNodeType(value);
    if (isEdit) collaboration.broadcastFieldUpdate("linkedNodeType", value);
  }, [isEdit, collaboration]);

  const handleSave = async () => {
    if (!title.trim()) return;
    setIsSaving(true);

    const snapshot: Record<string, unknown> = {
      title: title.trim(),
      slug: pageSlug.trim() || undefined,
      content,
      parent_id: parentId || null,
      tags,
      status,
      icon: icon.trim() || null,
      linked_node_type: linkedNodeType || null,
      ...(isEdit ? { change_summary: changeSummary.trim() || null } : {}),
    };

    try {
      // All saves go through the change request / draft system.
      // Only admins applying an approved CR writes to live data.
      await draftSave.save(snapshot);
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
    } catch (err) {
      console.error("Failed to save wiki page:", err);
    } finally {
      setIsSaving(false);
    }
  };

  if (isEdit && isLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  const userName = user?.display_name ?? user?.username ?? "Unknown";
  const userColor = getUserColor(user?.id ?? "");

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(isEdit ? `/wiki/${slug}` : "/wiki")}
            className="p-1.5 rounded-md hover:bg-[hsl(var(--accent))]"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-2xl font-bold">
            {isEdit ? "Edit Page" : "New Page"}
          </h1>
          {/* Collaboration status */}
          {isEdit && collaboration.isConnected && (
            <div className="flex items-center gap-1.5 ml-2">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                Live{collaboration.collaborators.length > 0 && ` (${collaboration.collaborators.length + 1} editors)`}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {hasDraft && activeDraft && activeDraft.status === "draft" && (
            <>
              <button
                onClick={handlePushToDev}
                disabled={isPushingToDev}
                className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-md hover:bg-teal-700 text-sm disabled:opacity-50"
              >
                <GitMerge className="w-4 h-4" />
                {isPushingToDev ? "Pushing..." : "Push to Dev"}
              </button>
              <button
                onClick={() => draftSave.submitForReview(activeDraft.id)}
                disabled={draftSave.isSubmitting}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                {draftSave.isSubmitting ? "Submitting..." : "Submit for Review"}
              </button>
            </>
          )}
          <button
            onClick={handleSave}
            disabled={isSaving || !title.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 text-sm disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            {isSaving ? "Saving..." : "Save as Draft"}
          </button>
        </div>
      </div>

      {/* Tier selector */}
      {isEdit && (
        <div className="mb-4">
          <TierSelector
            currentTier={entityVersion.sourceTier}
            selectedTier={entityVersion.selectedTier}
            onSelect={entityVersion.setTier}
          />
        </div>
      )}

      {/* Draft banner */}
      {hasDraft && (
        <div className="flex items-center gap-2 mb-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <GitBranch className="w-4 h-4 text-blue-400 shrink-0" />
          <span className="text-sm text-blue-300">
            You have an unpublished draft ({activeDraft?.status}).
            {activeDraft?.status === "rejected" && activeDraft?.review_comment && (
              <> Review comment: &ldquo;{activeDraft.review_comment}&rdquo;</>
            )}
          </span>
        </div>
      )}

      {/* Form fields */}
      <div className="grid gap-4 mb-6">
        <div className="grid grid-cols-[1fr_auto] gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              value={title}
              onChange={(e) => handleTitleChange(e.target.value)}
              placeholder="Page title"
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            />
          </div>
          <div className="w-20">
            <label className="block text-sm font-medium mb-1">Icon</label>
            <input
              value={icon}
              onChange={(e) => handleIconChange(e.target.value)}
              placeholder="e.g. emoji"
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm text-center"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Slug</label>
            <input
              value={pageSlug}
              onChange={(e) => setPageSlug(e.target.value)}
              placeholder="auto-generated"
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Parent Page</label>
            <select
              value={parentId}
              onChange={(e) => handleParentChange(e.target.value)}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value="">None (root level)</option>
              {parentOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {"  ".repeat(opt.depth)}{opt.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Tags</label>
            <TagInput
              value={tags}
              onChange={handleTagsChange}
              placeholder="e.g. playbook, phishing, onboarding"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Linked Node Type</label>
            <select
              value={linkedNodeType}
              onChange={(e) => handleLinkedNodeChange(e.target.value)}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value="">None</option>
              {nodeCatalog?.nodes
                ?.slice()
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((node) => (
                  <option key={node.type} value={node.type}>
                    {node.name} ({node.category})
                  </option>
                ))}
            </select>
            <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
              Links this wiki page as documentation for a graph node type
            </p>
          </div>
        </div>

        {isEdit && (
          <div>
            <label className="block text-sm font-medium mb-1">Change Summary (optional)</label>
            <input
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              placeholder="Describe what changed"
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            />
          </div>
        )}
      </div>

      {/* Content editor */}
      <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
        {isEdit && page ? (
          <CollaborativeMarkdownEditor
            collaboration={collaboration}
            userName={userName}
            userColor={userColor}
            placeholder="Start writing your wiki page content..."
            onChange={setContent}
            initialContent={activeDraft?.snapshot?.content as string | undefined}
          />
        ) : (
          <MarkdownEditor
            content={content}
            onChange={setContent}
            placeholder="Start writing your wiki page content..."
          />
        )}
      </div>
    </div>
  );
}
