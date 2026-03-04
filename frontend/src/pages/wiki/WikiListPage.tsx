import { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { BookOpen, Plus, Search, ChevronRight, ChevronDown, Tag } from "lucide-react";
import type { PaginatedResponse, WikiPageListItem, WikiTreeNode, WikiSearchResult } from "@/types/api";

// ─── Tree sidebar ───

function TreeNode({ node, depth = 0 }: { node: WikiTreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 px-2 rounded-md hover:bg-[hsl(var(--accent))] cursor-pointer text-sm group"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
            className="w-4 h-4 flex items-center justify-center shrink-0 text-[hsl(var(--muted-foreground))]"
          >
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
        ) : (
          <span className="w-4 shrink-0" />
        )}
        {node.icon && <span className="shrink-0">{node.icon}</span>}
        <Link
          to={`/wiki/${node.slug}`}
          className="truncate flex-1 text-[hsl(var(--foreground))] hover:text-[hsl(var(--primary))]"
        >
          {node.title}
        </Link>
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main page ───

export function WikiListPage() {
  const { hasPermission } = useAuthStore();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [tagFilter, setTagFilter] = useState("");
  const [search, setSearch] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);

  // Fetch tree for sidebar
  const { data: tree } = useQuery({
    queryKey: ["wiki-tree"],
    queryFn: () => api.get<WikiTreeNode[]>("/wiki/tree"),
  });

  // Fetch page list
  const { data, isLoading } = useQuery({
    queryKey: ["wiki-pages", statusFilter, tagFilter, search, page],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (tagFilter) params.set("tag", tagFilter);
      if (search) params.set("search", search);
      params.set("page", String(page));
      params.set("per_page", "25");
      return api.get<PaginatedResponse<WikiPageListItem>>(`/wiki?${params}`);
    },
  });

  // Full-text search results
  const { data: searchResults, isLoading: isSearching } = useQuery({
    queryKey: ["wiki-search", searchQuery],
    queryFn: () => api.get<PaginatedResponse<WikiSearchResult>>(`/wiki/search?q=${encodeURIComponent(searchQuery)}`),
    enabled: searchQuery.length > 0,
  });

  // Collect all unique tags from the page list for filter dropdown
  const allTags = useMemo(() => {
    if (!data?.data) return [];
    const tagSet = new Set<string>();
    data.data.forEach((p) => p.tags.forEach((t) => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [data]);

  const showSearchResults = searchQuery.length > 0;

  return (
    <div className="flex gap-6">
      {/* Tree sidebar */}
      <aside className="w-56 shrink-0 border-r border-[hsl(var(--border))] pr-4 max-h-[calc(100vh-8rem)] overflow-y-auto">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">Pages</p>
          {hasPermission("wiki:create") && (
            <Link
              to="/wiki/new"
              className="text-[hsl(var(--primary))] hover:opacity-80"
              title="New page"
            >
              <Plus className="w-4 h-4" />
            </Link>
          )}
        </div>
        {tree && tree.length > 0 ? (
          tree.map((node) => <TreeNode key={node.id} node={node} />)
        ) : (
          <p className="text-sm text-[hsl(var(--muted-foreground))]">No pages yet</p>
        )}
      </aside>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Wiki</h1>
          {hasPermission("wiki:create") && (
            <Link
              to="/wiki/new"
              className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 text-sm"
            >
              <Plus className="w-4 h-4" />
              New Page
            </Link>
          )}
        </div>

        {/* Search + filters */}
        <div className="flex gap-3 mb-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
            <input
              value={searchQuery || search}
              onChange={(e) => {
                const val = e.target.value;
                if (val.length >= 2) {
                  setSearchQuery(val);
                  setSearch("");
                } else {
                  setSearchQuery("");
                  setSearch(val);
                }
                setPage(1);
              }}
              placeholder="Search wiki pages..."
              className="w-full pl-9 pr-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
          >
            <option value="">All statuses</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
          {allTags.length > 0 && (
            <select
              value={tagFilter}
              onChange={(e) => { setTagFilter(e.target.value); setPage(1); }}
              className="px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
            >
              <option value="">All tags</option>
              {allTags.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          )}
        </div>

        {/* Full-text search results */}
        {showSearchResults ? (
          isSearching ? (
            <div className="text-center py-8">Searching...</div>
          ) : searchResults?.data.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-[hsl(var(--muted-foreground))]">
              <Search className="w-12 h-12 mb-3" />
              <p>No results found for &ldquo;{searchQuery}&rdquo;</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {searchResults?.data.map((result) => (
                <Link
                  key={result.id}
                  to={`/wiki/${result.slug}`}
                  className="border border-[hsl(var(--border))] rounded-lg p-4 hover:bg-[hsl(var(--accent))] transition-colors"
                >
                  <h3 className="font-medium">{result.title}</h3>
                  <p
                    className="text-sm text-[hsl(var(--muted-foreground))] mt-1 line-clamp-2"
                    dangerouslySetInnerHTML={{ __html: result.snippet }}
                  />
                  {result.tags.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {result.tags.map((t) => (
                        <span key={t} className="text-xs px-1.5 py-0.5 bg-[hsl(var(--accent))] rounded">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          )
        ) : isLoading ? (
          <div className="text-center py-8">Loading...</div>
        ) : data?.data.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-[hsl(var(--muted-foreground))]">
            <BookOpen className="w-12 h-12 mb-3" />
            <p>No wiki pages yet</p>
            {hasPermission("wiki:create") && (
              <button
                onClick={() => navigate("/wiki/new")}
                className="mt-3 text-sm text-[hsl(var(--primary))] hover:underline"
              >
                Create the first page
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="grid gap-3">
              {data?.data.map((pg) => (
                <Link
                  key={pg.id}
                  to={`/wiki/${pg.slug}`}
                  className="border border-[hsl(var(--border))] rounded-lg p-4 hover:bg-[hsl(var(--accent))] transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium flex items-center gap-2">
                      {pg.icon && <span>{pg.icon}</span>}
                      {pg.title}
                    </h3>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      pg.status === "published"
                        ? "bg-green-500/15 text-green-400"
                        : pg.status === "draft"
                        ? "bg-yellow-500/15 text-yellow-400"
                        : "bg-gray-500/15 text-gray-400"
                    }`}>
                      {pg.status}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-4 mt-2 text-sm text-[hsl(var(--muted-foreground))]">
                    <span>By {pg.created_by.display_name}</span>
                    {pg.child_count > 0 && <span>{pg.child_count} subpages</span>}
                    <span>v{pg.version}</span>
                    <span>Updated {formatDate(pg.updated_at)}</span>
                  </div>
                  {pg.tags.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {pg.tags.map((t) => (
                        <span key={t} className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 bg-[hsl(var(--accent))] rounded">
                          <Tag className="w-3 h-3" />
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {data && data.meta.total_pages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1 text-sm border border-[hsl(var(--border))] rounded-md disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-[hsl(var(--muted-foreground))]">
                  Page {page} of {data.meta.total_pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(data.meta.total_pages, p + 1))}
                  disabled={page >= data.meta.total_pages}
                  className="px-3 py-1 text-sm border border-[hsl(var(--border))] rounded-md disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
