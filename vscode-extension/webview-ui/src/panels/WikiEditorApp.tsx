/**
 * Wiki editor webview panel app.
 * Supports raw HTML editing and rendered preview mode.
 */

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getVsCodeApi } from "../vscode";

interface WikiPage {
  id: string;
  title: string;
  slug: string;
  content: string;
  status: string;
  version: number;
}

interface Props {
  pageId?: string;
  slug?: string;
}

type ViewMode = "edit" | "preview" | "split";

export function WikiEditorApp({ pageId, slug }: Props) {
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("edit");

  const { data: page, isLoading } = useQuery({
    queryKey: ["wiki-page", pageId || slug],
    queryFn: () => {
      if (pageId) return api.get<WikiPage>(`/wiki/${pageId}`);
      if (slug) return api.get<WikiPage>(`/wiki/by-slug/${slug}`);
      throw new Error("No page ID or slug");
    },
    enabled: !!(pageId || slug),
  });

  useEffect(() => {
    if (page) {
      setContent(page.content || "");
      setTitle(page.title);
    }
  }, [page]);

  // Listen for wiki state requests from the extension host (MCP bridge)
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const msg = event.data;
      if (msg.type === "wiki-state-request") {
        getVsCodeApi().postMessage({
          type: "wiki-state-response",
          data: {
            pageId: page?.id || pageId,
            title,
            slug: page?.slug || slug,
            content,
            version: page?.version,
          },
        });
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [page, pageId, slug, title, content]);

  const handleSave = async () => {
    if (!page) return;
    setSaving(true);
    try {
      await api.patch(`/wiki/${page.id}`, { content, title });
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--vscode-foreground)" }}>
        Loading wiki page...
      </div>
    );
  }

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "4px 12px",
    fontSize: 12,
    border: "none",
    borderRadius: 3,
    cursor: "pointer",
    background: active ? "var(--vscode-button-background)" : "transparent",
    color: active ? "var(--vscode-button-foreground)" : "var(--vscode-foreground)",
    opacity: active ? 1 : 0.7,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--vscode-editor-background)", color: "var(--vscode-foreground)" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px", borderBottom: "1px solid var(--vscode-panel-border)" }}>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={{
            flex: 1,
            fontSize: 18,
            fontWeight: 600,
            background: "transparent",
            color: "var(--vscode-foreground)",
            border: "none",
            outline: "none",
          }}
        />
        {/* View mode toggle */}
        <div style={{ display: "flex", gap: 2, background: "var(--vscode-editor-background)", border: "1px solid var(--vscode-panel-border)", borderRadius: 4, padding: 2 }}>
          <button style={tabStyle(viewMode === "edit")} onClick={() => setViewMode("edit")} title="Edit source">
            Edit
          </button>
          <button style={tabStyle(viewMode === "split")} onClick={() => setViewMode("split")} title="Side-by-side">
            Split
          </button>
          <button style={tabStyle(viewMode === "preview")} onClick={() => setViewMode("preview")} title="Preview rendered">
            Preview
          </button>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            padding: "6px 16px",
            background: "var(--vscode-button-background)",
            color: "var(--vscode-button-foreground)",
            border: "none",
            borderRadius: 4,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      {/* Content area */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Editor pane */}
        {(viewMode === "edit" || viewMode === "split") && (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={{
              flex: 1,
              padding: 16,
              background: "var(--vscode-editor-background)",
              color: "var(--vscode-editor-foreground)",
              border: "none",
              outline: "none",
              fontFamily: "var(--vscode-editor-font-family)",
              fontSize: "var(--vscode-editor-font-size)",
              lineHeight: 1.6,
              resize: "none",
              borderRight: viewMode === "split" ? "1px solid var(--vscode-panel-border)" : "none",
            }}
            placeholder="Start writing..."
          />
        )}

        {/* Preview pane */}
        {(viewMode === "preview" || viewMode === "split") && (
          <div
            style={{
              flex: 1,
              padding: 16,
              overflow: "auto",
              lineHeight: 1.6,
              fontSize: "var(--vscode-editor-font-size)",
            }}
            className="wiki-preview"
            dangerouslySetInnerHTML={{ __html: content }}
          />
        )}
      </div>
    </div>
  );
}
