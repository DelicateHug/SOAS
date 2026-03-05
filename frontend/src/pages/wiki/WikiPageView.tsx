import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { DocumentationViewer } from "@/components/DocumentationViewer";
import { Edit, Clock, Tag, ChevronRight, BookOpen, Trash2, Users } from "lucide-react";
import { DynamicIcon } from "@/components/ui/DynamicIcon";
import { NodePreview } from "@/components/wiki/NodePreview";
import type { WikiPage, WikiBreadcrumb, WikiPageListItem, PaginatedResponse } from "@/types/api";

export function WikiPageView() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { hasPermission } = useAuthStore();

  const { data: page, isLoading, error } = useQuery({
    queryKey: ["wiki-page", slug],
    queryFn: () => api.get<WikiPage>(`/wiki/by-slug/${slug}`),
    enabled: !!slug,
  });

  const { data: breadcrumbs } = useQuery({
    queryKey: ["wiki-breadcrumbs", page?.id],
    queryFn: () => api.get<WikiBreadcrumb[]>(`/wiki/${page!.id}/breadcrumbs`),
    enabled: !!page?.id,
  });

  const { data: childPagesData } = useQuery({
    queryKey: ["wiki-children", page?.id],
    queryFn: () => api.get<PaginatedResponse<WikiPageListItem>>(`/wiki?parent_id=${page!.id}&per_page=50`),
    enabled: !!page?.id && (page?.child_count ?? 0) > 0,
  });

  const childPages = childPagesData?.data.map((c) => ({
    title: c.title,
    slug: c.slug,
    icon: c.icon,
  }));

  const handleDelete = async () => {
    if (!page) return;
    if (!confirm("Are you sure you want to delete this wiki page?")) return;
    await api.delete(`/wiki/${page.id}`);
    navigate("/wiki");
  };

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (error || !page) {
    return (
      <div className="flex flex-col items-center py-12 text-[hsl(var(--muted-foreground))]">
        <BookOpen className="w-12 h-12 mb-3" />
        <p>Wiki page not found</p>
        <Link to="/wiki" className="mt-3 text-sm text-[hsl(var(--primary))] hover:underline">
          Back to wiki
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 1 && (
        <nav className="flex items-center gap-1 text-sm text-[hsl(var(--muted-foreground))] mb-4">
          <Link to="/wiki" className="hover:text-[hsl(var(--foreground))]">Wiki</Link>
          {breadcrumbs.map((crumb, i) => (
            <span key={crumb.id} className="flex items-center gap-1">
              <ChevronRight className="w-3 h-3" />
              {i === breadcrumbs.length - 1 ? (
                <span className="text-[hsl(var(--foreground))]">{crumb.title}</span>
              ) : (
                <Link
                  to={`/wiki/${crumb.slug}`}
                  className="hover:text-[hsl(var(--foreground))]"
                >
                  {crumb.title}
                </Link>
              )}
            </span>
          ))}
        </nav>
      )}

      {/* Header */}
      <div className="flex items-start justify-between mb-0.5">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <DynamicIcon name={page.icon} className="w-6 h-6 shrink-0" />
            {page.title}
          </h1>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-[hsl(var(--muted-foreground))]">
            <span className={`px-2 py-0.5 rounded text-xs ${
              page.status === "published"
                ? "bg-green-500/15 text-green-400"
                : page.status === "draft"
                ? "bg-yellow-500/15 text-yellow-400"
                : "bg-gray-500/15 text-gray-400"
            }`}>
              {page.status}
            </span>
            <span>v{page.version}</span>
            <span>By {page.created_by.display_name}</span>
            {page.updated_by && (
              <span>Updated by {page.updated_by.display_name}</span>
            )}
            <span>Updated {formatDate(page.updated_at)}</span>
            {page.child_count > 0 && (
              <span>{page.child_count} subpages</span>
            )}
            {page.active_editors > 0 && (
              <span className="flex items-center gap-1 text-green-400">
                <Users className="w-3.5 h-3.5" />
                {page.active_editors} editing now
              </span>
            )}
          </div>
        </div>

        {/* Node preview in header gap */}
        {page.linked_node_type && (
          <NodePreview nodeType={page.linked_node_type} compact />
        )}

        <div className="flex items-center gap-2 shrink-0">
          <Link
            to={`/wiki/${slug}/history`}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))]"
          >
            <Clock className="w-4 h-4" />
            History
          </Link>
          {hasPermission("wiki:update") && (
            <Link
              to={`/wiki/${slug}/edit`}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90"
            >
              <Edit className="w-4 h-4" />
              Edit
            </Link>
          )}
          {hasPermission("wiki:delete") && (
            <button
              onClick={handleDelete}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-500/30 text-red-400 rounded-md hover:bg-red-500/10"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Tags */}
      {page.tags.length > 0 && (
        <div className="flex gap-1.5">
          {page.tags.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 bg-[hsl(var(--accent))] rounded"
            >
              <Tag className="w-3 h-3" />
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="border border-[hsl(var(--border))] rounded-lg pt-3 px-6 pb-6">
        {page.content ? (
          <DocumentationViewer content={page.content} childPages={childPages} />
        ) : (
          <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
            This page has no content yet.{" "}
            {hasPermission("wiki:update") && (
              <Link to={`/wiki/${slug}/edit`} className="text-[hsl(var(--primary))] hover:underline">
                Start writing
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
