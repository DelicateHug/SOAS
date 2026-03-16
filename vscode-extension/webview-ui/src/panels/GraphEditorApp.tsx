/**
 * Graph editor webview panel app.
 * Wraps the existing GraphEditor component with webview-specific initialization.
 */

import { useEffect, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { GraphEditor } from "@/components/graph-editor/GraphEditor";
import { useGraphEditorStore } from "@/components/graph-editor/stores/graphEditorStore";
import { useNodeCatalog } from "@/components/graph-editor/hooks/useNodeCatalog";
import { getVsCodeApi } from "../vscode";

interface AutomationDetail {
  id: string;
  name: string;
  description: string;
  status: string;
  version: number;
  graph_data?: Record<string, unknown>;
  parameters: Array<{ name: string; type: string; default?: string }>;
  timeout_seconds: number;
  trigger_tags: string[];
  is_trigger_enabled: boolean;
}

interface Props {
  automationId?: string;
}

export function GraphEditorApp({ automationId }: Props) {
  const { data: catalog, isLoading: isCatalogLoading } = useNodeCatalog();
  const loadFromVP2GraphData = useGraphEditorStore((s) => s.loadFromVP2GraphData);
  const addNode = useGraphEditorStore((s) => s.addNode);
  const setNodes = useGraphEditorStore((s) => s.setNodes);
  const setEdges = useGraphEditorStore((s) => s.setEdges);
  const setName = useGraphEditorStore((s) => s.setName);
  const setDescription = useGraphEditorStore((s) => s.setDescription);
  const setGraphId = useGraphEditorStore((s) => s.setGraphId);
  const setTriggerTags = useGraphEditorStore((s) => s.setTriggerTags);
  const updateStartNodeOutputs = useGraphEditorStore((s) => s.updateStartNodeOutputs);
  const setIsDirty = useGraphEditorStore((s) => s.setIsDirty);

  const [initialized, setInitialized] = useState(false);

  const { data: automation, isLoading: isAutomationLoading } = useQuery({
    queryKey: ["automation", automationId],
    queryFn: () => api.get<AutomationDetail>(`/automations/${automationId}`),
    enabled: !!automationId,
  });

  const handleCreateAutomation = useCallback(async (): Promise<string> => {
    const name = useGraphEditorStore.getState().name || "Untitled Automation";
    const result = await api.post<{ id: string }>("/automations", { name });
    setGraphId(result.id);
    return result.id;
  }, [setGraphId]);

  useEffect(() => {
    if (initialized) return;
    if (isCatalogLoading || !catalog) return;
    if (automationId && isAutomationLoading) return;

    const startEntry = catalog.find(
      (c) => c.type === "trigger_start" || c.type === "start"
    );

    if (automation && automationId) {
      setGraphId(automationId);
      setName(automation.name);
      setDescription(automation.description || "");
      setTriggerTags(automation.trigger_tags || []);

      if (automation.graph_data && Object.keys(automation.graph_data).length > 0) {
        loadFromVP2GraphData(automation.graph_data, catalog);

        if (automation.parameters?.length > 0) {
          updateStartNodeOutputs(automation.parameters);
        }
      } else if (startEntry) {
        addNode(startEntry, { x: 250, y: 250 });
      }
    } else {
      // New automation
      if (startEntry) {
        addNode(startEntry, { x: 250, y: 250 });
      }
    }

    setIsDirty(false);
    setInitialized(true);
  }, [
    initialized, catalog, isCatalogLoading, automation, automationId,
    isAutomationLoading, setGraphId, setName, setDescription, setTriggerTags,
    loadFromVP2GraphData, setNodes, setEdges, addNode, updateStartNodeOutputs,
    setIsDirty,
  ]);

  // Listen for graph state requests and graph load pushes from the extension host
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const msg = event.data;

      if (msg.type === "graph-state-request") {
        // Extension host is requesting current graph state — send it back
        const state = useGraphEditorStore.getState();
        const graphData = state.toVP2GraphData();
        const response = {
          automationId: state.graphId,
          name: state.name,
          description: state.description,
          graphData,
        };
        getVsCodeApi().postMessage({
          type: "graph-state-response",
          data: response,
        });
      } else if (msg.type === "graph-load" && msg.data && catalog) {
        // Extension host is pushing new graph data to load
        const store = useGraphEditorStore.getState();
        store.loadFromVP2GraphData(msg.data, catalog);
        store.setIsDirty(true);
      }
    };

    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [catalog]);

  if (isCatalogLoading || (automationId && isAutomationLoading)) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "var(--vscode-foreground)" }}>
        Loading graph editor...
      </div>
    );
  }

  return (
    <div style={{ width: "100vw", height: "100vh", overflow: "hidden" }}>
      <GraphEditor
        automationId={automationId}
        automationVersion={automation?.version ?? 1}
        onCreateAutomation={handleCreateAutomation}
      />
    </div>
  );
}
