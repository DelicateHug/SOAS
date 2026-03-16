/**
 * Route page component for the graph editor.
 * Supports both creating new automations and editing existing ones.
 *
 * Routes:
 *   /automations/new         -> New empty graph with a Start node
 *   /automations/:id/editor  -> Edit existing automation's graph
 */

import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ArrowLeft, Loader2 } from "lucide-react";
import { GraphEditor } from "@/components/graph-editor/GraphEditor";
import { useGraphEditorStore } from "@/components/graph-editor/stores/graphEditorStore";
import { useNodeCatalog } from "@/components/graph-editor/hooks/useNodeCatalog";
import type { VP2GraphData } from "@/components/graph-editor/types/graph";
import type { AutomationItem } from "@/types/api";
import { useTeamStore } from "@/stores/teamStore";

interface AutomationDetail extends AutomationItem {
  graph_file?: string;
  // Graph data may be in either frontend or backend format
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  graph_data?: VP2GraphData | Record<string, any>;
  script_hash?: string;
  parameters: Array<{ name: string; type: string; default?: string }>;
  timeout_seconds: number;
  trigger_tags: string[];
  is_trigger_enabled: boolean;
}

export function GraphEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id;

  const { data: catalog, isLoading: isCatalogLoading } = useNodeCatalog();
  const loadFromVP2GraphData = useGraphEditorStore(
    (s) => s.loadFromVP2GraphData
  );
  const addNode = useGraphEditorStore((s) => s.addNode);
  const setNodes = useGraphEditorStore((s) => s.setNodes);
  const setEdges = useGraphEditorStore((s) => s.setEdges);
  const setName = useGraphEditorStore((s) => s.setName);
  const setDescription = useGraphEditorStore((s) => s.setDescription);
  const setGraphId = useGraphEditorStore((s) => s.setGraphId);
  const setTriggerTags = useGraphEditorStore((s) => s.setTriggerTags);
  const updateStartNodeOutputs = useGraphEditorStore(
    (s) => s.updateStartNodeOutputs
  );
  const setIsDirty = useGraphEditorStore((s) => s.setIsDirty);

  const [automationId, setAutomationId] = useState<string | undefined>(id);
  const [initialized, setInitialized] = useState(false);

  // Fetch existing automation if editing
  const { data: automation, isLoading: isAutomationLoading } = useQuery({
    queryKey: ["automation", id],
    queryFn: () => api.get<AutomationDetail>(`/automations/${id}`),
    enabled: !!id,
  });

  const activeTeamId = useTeamStore((s) => s.activeTeamId);

  // Called by GraphEditor on first save when no automation exists yet
  const handleCreateAutomation = useCallback(async (): Promise<string> => {
    const name = useGraphEditorStore.getState().name || "Untitled Automation";
    const result = await api.post<{ id: string }>("/automations", {
      name,
      team_id: activeTeamId ?? undefined,
    });
    const newId = result.id;
    setAutomationId(newId);
    setGraphId(newId);
    window.history.replaceState(null, "", `/automations/${newId}/editor`);
    return newId;
  }, [setGraphId, activeTeamId]);

  // Initialize the graph editor once catalog and (optionally) automation data are loaded
  useEffect(() => {
    if (initialized) return;
    if (isCatalogLoading || !catalog) return;

    if (isNew) {
      // New graph: clear any stale state from a previously loaded graph
      setNodes([]);
      setEdges([]);

      const startEntry = catalog.find(
        (c) => c.type === "trigger_start" || c.type === "start"
      );

      setName("Untitled Automation");
      setDescription("");
      setGraphId("");
      setTriggerTags([]);

      if (startEntry) {
        addNode(startEntry, { x: 250, y: 250 });
      }

      setInitialized(true);
    } else if (automation) {
      // If the store already has this automation loaded with data,
      // don't overwrite with potentially stale React Query cache.
      // This preserves correctly saved data when navigating back.
      const currentStore = useGraphEditorStore.getState();
      if (currentStore.graphId === id && currentStore.nodes.length > 0) {
        setInitialized(true);
        return;
      }

      // Existing graph: load from stored data
      if (automation.graph_data) {
        loadFromVP2GraphData(automation.graph_data, catalog);
      } else {
        // No graph data yet - start with empty canvas
        setName(automation.name);
        setDescription(automation.description || "");
        setGraphId(automation.id);
        setTriggerTags(automation.trigger_tags || []);

        // Add a Start node if the catalog has one
        const startEntry = catalog.find(
          (c) => c.type === "trigger_start" || c.type === "start"
        );
        if (startEntry) {
          addNode(startEntry, { x: 250, y: 250 });
        }
      }
      setInitialized(true);
    }
  }, [
    initialized,
    isNew,
    isCatalogLoading,
    catalog,
    automation,
    loadFromVP2GraphData,
    addNode,
    setNodes,
    setEdges,
    setName,
    setDescription,
    setGraphId,
    setTriggerTags,
  ]);

  // Sync Start node dynamic outputs with automation parameters after load
  useEffect(() => {
    if (!initialized || isNew || !automation?.parameters) return;

    const store = useGraphEditorStore.getState();
    const startNode = store.nodes.find(
      (n) => (n.data as { type: string }).type === "start"
    );
    if (!startNode) return;

    const currentDefs = ((startNode.data as { properties: Record<string, unknown> }).properties?._input_defs || []) as Array<{ name: string }>;
    const automationParams = automation.parameters || [];

    // Compare by name set to detect mismatches
    const currentNames = JSON.stringify([...currentDefs.map((d) => d.name)].sort());
    const targetNames = JSON.stringify([...automationParams.map((p) => p.name)].sort());

    if (currentNames !== targetNames && automationParams.length > 0) {
      updateStartNodeOutputs(
        automationParams.map((p) => ({
          name: p.name,
          type: p.type || "STRING",
          required: true,
          default_value: (p.default as unknown) ?? null,
          description: "",
        }))
      );
      // Don't mark as dirty since this is an initial sync
      setIsDirty(false);
    }
  }, [initialized, isNew, automation, updateStartNodeOutputs, setIsDirty]);

  // Show loading state
  if (isCatalogLoading || (!isNew && isAutomationLoading)) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <div className="flex flex-col items-center gap-3 text-[hsl(var(--muted-foreground))]">
          <Loader2 className="w-8 h-8 animate-spin" />
          <p className="text-sm">
            Loading {isNew ? "editor" : "automation"}...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col -m-6">
      {/* Breadcrumb / back nav */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[hsl(var(--border))] bg-[hsl(var(--background))] text-xs">
        <button
          onClick={() =>
            navigate(
              automationId
                ? `/automations/${automationId}`
                : "/automations"
            )
          }
          className="flex items-center gap-1 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
        >
          <ArrowLeft className="w-3 h-3" />
          {automationId ? "Back to automation" : "Back to automations"}
        </button>
        <span className="text-[hsl(var(--muted-foreground))]">/</span>
        <span className="font-medium">
          {isNew ? "New Automation" : "Graph Editor"}
        </span>
      </div>

      {/* Editor */}
      <div className="flex-1 min-h-0">
        <GraphEditor automationId={automationId} automationVersion={automation?.version ?? 1} onCreateAutomation={isNew ? handleCreateAutomation : undefined} />
      </div>
    </div>
  );
}
