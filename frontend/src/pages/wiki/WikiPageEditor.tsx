import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { TagInput } from "@/components/ui/TagInput";
import { Save, ArrowLeft } from "lucide-react";
import type { WikiPage, WikiTreeNode } from "@/types/api";

export function WikiPageEditor() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEdit = !!slug;

  const [title, setTitle] = useState("");
  const [pageSlug, setPageSlug] = useState("");
  const [content, setContent] = useState("");
  const [parentId, setParentId] = useState<string>("");
  const [tags, setTags] = useState<string[]>([]);
  const [status, setStatus] = useState("published");
  const [icon, setIcon] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Load existing page for editing
  const { data: page, isLoading } = useQuery({
    queryKey: ["wiki-page", slug],
    queryFn: () => api.get<WikiPage>(`/wiki/by-slug/${slug}`),
    enabled: isEdit,
  });

  // Load tree for parent selector
  const { data: tree } = useQuery({
    queryKey: ["wiki-tree"],
    queryFn: () => api.get<WikiTreeNode[]>("/wiki/tree"),
  });

  // Populate form when page loads
  useEffect(() => {
    if (page) {
      setTitle(page.title);
      setPageSlug(page.slug);
      setContent(page.content || "");
      setParentId(page.parent_id || "");
      setTags(page.tags);
      setStatus(page.status);
      setIcon(page.icon || "");
    }
  }, [page]);

  // Flatten tree for parent selector
  function flattenTree(nodes: WikiTreeNode[], depth = 0): Array<{ id: string; title: string; depth: number }> {
    const items: Array<{ id: string; title: string; depth: number }> = [];
    for (const node of nodes) {
      // Don't show current page as a parent option
      if (page && node.id === page.id) continue;
      items.push({ id: node.id, title: node.title, depth });
      items.push(...flattenTree(node.children, depth + 1));
    }
    return items;
  }

  const parentOptions = tree ? flattenTree(tree) : [];

  const handleSave = async () => {
    if (!title.trim()) return;
    setIsSaving(true);

    try {
      if (isEdit && page) {
        await api.patch(`/wiki/${page.id}`, {
          title: title.trim(),
          slug: pageSlug.trim() || undefined,
          content,
          parent_id: parentId || null,
          tags,
          status,
          icon: icon.trim() || null,
          change_summary: changeSummary.trim() || null,
        });
        queryClient.invalidateQueries({ queryKey: ["wiki-page", slug] });
        queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
        queryClient.invalidateQueries({ queryKey: ["wiki-pages"] });
        navigate(`/wiki/${pageSlug || slug}`);
      } else {
        const created = await api.post<WikiPage>("/wiki", {
          title: title.trim(),
          slug: pageSlug.trim() || undefined,
          content,
          parent_id: parentId || null,
          tags,
          status,
          icon: icon.trim() || null,
        });
        queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
        queryClient.invalidateQueries({ queryKey: ["wiki-pages"] });
        navigate(`/wiki/${created.slug}`);
      }
    } catch (err) {
      console.error("Failed to save wiki page:", err);
    } finally {
      setIsSaving(false);
    }
  };

  if (isEdit && isLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

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
        </div>
        <button
          onClick={handleSave}
          disabled={isSaving || !title.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 text-sm disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {isSaving ? "Saving..." : "Save"}
        </button>
      </div>

      {/* Form fields */}
      <div className="grid gap-4 mb-6">
        <div className="grid grid-cols-[1fr_auto] gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Page title"
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            />
          </div>
          <div className="w-20">
            <label className="block text-sm font-medium mb-1">Icon</label>
            <input
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
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
              onChange={(e) => setParentId(e.target.value)}
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
              onChange={(e) => setStatus(e.target.value)}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Tags</label>
          <TagInput
            value={tags}
            onChange={setTags}
            placeholder="e.g. playbook, phishing, onboarding"
          />
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
        <MarkdownEditor
          content={content}
          onChange={setContent}
          placeholder="Start writing your wiki page content..."
        />
      </div>
    </div>
  );
}
