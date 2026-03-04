/**
 * Left panel showing all available node types grouped by category.
 * Supports search/filter and drag-to-add or click-to-add.
 * Integrates Code Library blocks under the "Custom" category.
 */

import { useState, useMemo, useCallback, type DragEvent } from "react";
import { Search, GripVertical, ChevronRight, ChevronDown, PanelLeftClose, Star, Library } from "lucide-react";
import { useNodeCatalog } from "./hooks/useNodeCatalog";
import { useCodeLibraryPalette, useToggleFavorite, type CodeLibraryPaletteEntry } from "./hooks/useCodeLibrary";
import { useGraphEditorStore } from "./stores/graphEditorStore";
import type { NodeCatalogEntry, VP2Port, NodePropertyDef } from "./types/graph";

interface NodePaletteProps {
  onCollapse?: () => void;
}

/** Map a library palette entry to a NodeCatalogEntry for the graph editor */
function mapLibraryEntry(entry: CodeLibraryPaletteEntry): NodeCatalogEntry {
  return {
    type: entry.type,
    label: entry.name,
    category: entry.category,
    description: entry.description,
    color: entry.color,
    inputs: entry.input_ports.map((p) => ({
      name: p.name,
      type: p.type as VP2Port["type"],
      label: p.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    })),
    outputs: entry.output_ports.map((p) => ({
      name: p.name,
      type: p.type as VP2Port["type"],
      label: p.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    })),
    properties: entry.properties.map((p) => ({
      name: p.name,
      label: p.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      type: (p.ui_type === "code" ? "code" : p.ui_type === "select" ? "select" : "string") as NodePropertyDef["type"],
      default: p.default_value,
    })),
  };
}

/** Extended entry for rendering with library metadata */
interface PaletteItem {
  entry: NodeCatalogEntry;
  isLibrary?: boolean;
  libraryBlockId?: string;
  isFavorited?: boolean;
  creatorName?: string;
  subcategory?: string | null;
}

export function NodePalette({ onCollapse }: NodePaletteProps) {
  const { data: catalog, isLoading: isCatalogLoading } = useNodeCatalog();
  const { data: libraryBlocks, isLoading: isLibraryLoading } = useCodeLibraryPalette();
  const addNode = useGraphEditorStore((s) => s.addNode);
  const toggleFavorite = useToggleFavorite();
  const [searchQuery, setSearchQuery] = useState("");
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(
    new Set()
  );

  const isLoading = isCatalogLoading || isLibraryLoading;

  // Build palette items: catalog nodes + library blocks
  const { grouped, favorites } = useMemo(() => {
    const items: PaletteItem[] = [];

    // Add catalog entries
    if (catalog) {
      const filtered = searchQuery
        ? catalog.filter(
            (entry) =>
              entry.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
              entry.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
              entry.description.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : catalog;
      for (const entry of filtered) {
        items.push({ entry });
      }
    }

    // Add library blocks
    const favItems: PaletteItem[] = [];
    if (libraryBlocks) {
      for (const lb of libraryBlocks) {
        const matchesSearch =
          !searchQuery ||
          lb.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          lb.description.toLowerCase().includes(searchQuery.toLowerCase());

        if (matchesSearch) {
          const item: PaletteItem = {
            entry: mapLibraryEntry(lb),
            isLibrary: true,
            libraryBlockId: lb.library_block_id,
            isFavorited: lb.is_favorited,
            creatorName: lb.creator_name,
            subcategory: lb.subcategory,
          };
          items.push(item);
          if (lb.is_favorited) {
            favItems.push(item);
          }
        }
      }
    }

    // Group by category (with subcategory nesting for library blocks)
    const groups: Record<string, PaletteItem[]> = {};
    for (const item of items) {
      let cat = item.entry.category || "Uncategorized";
      // For library blocks with subcategories, create nested group key
      if (item.isLibrary && item.subcategory) {
        cat = `Custom > ${item.subcategory}`;
      }
      if (!groups[cat]) groups[cat] = [];
      groups[cat]!.push(item);
    }

    return { grouped: groups, favorites: favItems };
  }, [catalog, libraryBlocks, searchQuery]);

  const toggleCategory = useCallback((category: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  }, []);

  const handleDragStart = useCallback(
    (event: DragEvent<HTMLDivElement>, entry: NodeCatalogEntry) => {
      event.dataTransfer.setData(
        "application/graph-editor-node",
        JSON.stringify(entry)
      );
      event.dataTransfer.effectAllowed = "move";
    },
    []
  );

  const handleClickAdd = useCallback(
    (entry: NodeCatalogEntry) => {
      addNode(entry, { x: 400 + Math.random() * 100, y: 300 + Math.random() * 100 });
    },
    [addNode]
  );

  const renderItem = (item: PaletteItem) => (
    <div
      key={item.isLibrary ? `lib-${item.libraryBlockId}` : item.entry.type}
      draggable
      onDragStart={(e) => handleDragStart(e, item.entry)}
      onClick={() => handleClickAdd(item.entry)}
      className="flex items-center gap-2 px-2 py-1.5 rounded-md cursor-grab active:cursor-grabbing hover:bg-[hsl(var(--accent))] transition-colors group"
      title={item.isLibrary ? `${item.entry.description}\nby ${item.creatorName}` : item.entry.description}
    >
      <GripVertical className="w-3 h-3 text-[hsl(var(--muted-foreground))] opacity-0 group-hover:opacity-100 transition-opacity" />
      <div
        className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
        style={{ backgroundColor: item.entry.color }}
      />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium truncate">
          {item.entry.label}
        </p>
      </div>
      {item.isLibrary && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (item.libraryBlockId) toggleFavorite.mutate(item.libraryBlockId);
          }}
          className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          title={item.isFavorited ? "Remove favorite" : "Add favorite"}
        >
          <Star
            className={`w-3 h-3 ${
              item.isFavorited ? "fill-yellow-400 text-yellow-400" : "text-[hsl(var(--muted-foreground))]"
            }`}
          />
        </button>
      )}
    </div>
  );

  // Sort categories: put "Custom" and subcategories at the end
  const sortedCategories = useMemo(() => {
    return Object.entries(grouped).sort(([a], [b]) => {
      const aIsCustom = a === "Custom" || a.startsWith("Custom >");
      const bIsCustom = b === "Custom" || b.startsWith("Custom >");
      if (aIsCustom && !bIsCustom) return 1;
      if (!aIsCustom && bIsCustom) return -1;
      return a.localeCompare(b);
    });
  }, [grouped]);

  return (
    <div className="w-48 border-r border-[hsl(var(--border))] bg-[hsl(var(--background))] flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-2 border-b border-[hsl(var(--border))]">
        <div className="flex items-center justify-between mb-1.5">
          <h2 className="text-xs font-semibold">Nodes</h2>
          {onCollapse && (
            <button
              onClick={onCollapse}
              className="p-0.5 hover:bg-[hsl(var(--accent))] rounded"
              title="Collapse panel"
            >
              <PanelLeftClose className="w-3.5 h-3.5 text-[hsl(var(--muted-foreground))]" />
            </button>
          )}
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[hsl(var(--muted-foreground))]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search nodes..."
            className="w-full pl-7 pr-2 py-1.5 text-xs border border-[hsl(var(--input))] rounded-md bg-transparent"
          />
        </div>
      </div>

      {/* Node list */}
      <div className="flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="text-center py-4 text-xs text-[hsl(var(--muted-foreground))]">
            Loading catalog...
          </div>
        ) : Object.keys(grouped).length === 0 ? (
          <div className="text-center py-4 text-xs text-[hsl(var(--muted-foreground))]">
            {searchQuery ? "No matching nodes" : "No nodes available"}
          </div>
        ) : (
          <>
            {/* Favorites section */}
            {favorites.length > 0 && !searchQuery && (
              <div className="mb-2">
                <button
                  onClick={() => toggleCategory("__favorites__")}
                  className="flex items-center gap-1 w-full text-left px-1 py-1 text-xs font-semibold text-yellow-500 uppercase tracking-wider hover:text-yellow-400"
                >
                  {collapsedCategories.has("__favorites__") ? (
                    <ChevronRight className="w-3 h-3" />
                  ) : (
                    <ChevronDown className="w-3 h-3" />
                  )}
                  <Star className="w-3 h-3 fill-current" />
                  Favorites
                  <span className="ml-auto text-[10px] font-normal">
                    {favorites.length}
                  </span>
                </button>
                {!collapsedCategories.has("__favorites__") && (
                  <div className="space-y-1 mt-1">
                    {favorites.map(renderItem)}
                  </div>
                )}
              </div>
            )}

            {/* Category groups */}
            {sortedCategories.map(([category, items]) => (
              <div key={category} className="mb-2">
                <button
                  onClick={() => toggleCategory(category)}
                  className={`flex items-center gap-1 w-full text-left px-1 py-1 text-xs font-semibold uppercase tracking-wider hover:text-[hsl(var(--foreground))] ${
                    category === "Custom" || category.startsWith("Custom >")
                      ? "text-green-500"
                      : "text-[hsl(var(--muted-foreground))]"
                  }`}
                >
                  {collapsedCategories.has(category) ? (
                    <ChevronRight className="w-3 h-3" />
                  ) : (
                    <ChevronDown className="w-3 h-3" />
                  )}
                  {(category === "Custom" || category.startsWith("Custom >")) && (
                    <Library className="w-3 h-3" />
                  )}
                  {category.startsWith("Custom > ") ? category.slice(9) : category}
                  <span className="ml-auto text-[10px] font-normal">
                    {items.length}
                  </span>
                </button>

                {!collapsedCategories.has(category) && (
                  <div className="space-y-1 mt-1">
                    {items.map(renderItem)}
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
