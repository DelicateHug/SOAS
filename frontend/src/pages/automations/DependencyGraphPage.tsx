import { useCallback, useEffect, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  Handle,
  useNodesState,
  useEdgesState,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "@/lib/api";
import { ArrowLeft } from "lucide-react";
import type { DependencyGraphData } from "@/types/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NODE_WIDTH = 220;
const NODE_HEIGHT = 80;
const HORIZONTAL_SPACING = 280;
const VERTICAL_SPACING = 120;

// ---------------------------------------------------------------------------
// Auto-layout: BFS-based layered positioning
// ---------------------------------------------------------------------------

function computeLayout(
  graphNodes: DependencyGraphData["nodes"],
  graphEdges: DependencyGraphData["edges"]
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  // Build adjacency & track incoming edges
  const incomingCount = new Map<string, number>();
  const adjacency = new Map<string, string[]>();

  for (const n of graphNodes) {
    incomingCount.set(n.id, 0);
    adjacency.set(n.id, []);
  }

  for (const e of graphEdges) {
    adjacency.get(e.source)?.push(e.target);
    incomingCount.set(e.target, (incomingCount.get(e.target) ?? 0) + 1);
  }

  // Find root nodes (no incoming edges)
  const roots = graphNodes
    .filter((n) => (incomingCount.get(n.id) ?? 0) === 0)
    .map((n) => n.id);

  // If no roots exist (cycles), just start with the first node
  if (roots.length === 0 && graphNodes.length > 0) {
    roots.push(graphNodes[0]!.id);
  }

  // BFS to assign layers
  const layerMap = new Map<string, number>();
  const visited = new Set<string>();
  const queue: Array<{ id: string; layer: number }> = [];

  for (const root of roots) {
    queue.push({ id: root, layer: 0 });
    visited.add(root);
    layerMap.set(root, 0);
  }

  while (queue.length > 0) {
    const { id, layer } = queue.shift()!;
    const children = adjacency.get(id) ?? [];
    for (const child of children) {
      // Always take the deepest layer assignment
      const existingLayer = layerMap.get(child) ?? -1;
      const newLayer = layer + 1;
      if (newLayer > existingLayer) {
        layerMap.set(child, newLayer);
      }
      if (!visited.has(child)) {
        visited.add(child);
        queue.push({ id: child, layer: newLayer });
      }
    }
  }

  // Place any unvisited nodes (disconnected components) in layer 0
  for (const n of graphNodes) {
    if (!layerMap.has(n.id)) {
      layerMap.set(n.id, 0);
    }
  }

  // Group nodes by layer
  const layers = new Map<number, string[]>();
  for (const [nodeId, layer] of layerMap) {
    if (!layers.has(layer)) {
      layers.set(layer, []);
    }
    layers.get(layer)!.push(nodeId);
  }

  // Position nodes layer by layer
  const sortedLayers = Array.from(layers.keys()).sort((a, b) => a - b);
  for (const layer of sortedLayers) {
    const nodesInLayer = layers.get(layer)!;
    const layerHeight = nodesInLayer.length * VERTICAL_SPACING;
    const startY = -layerHeight / 2 + VERTICAL_SPACING / 2;

    nodesInLayer.forEach((nodeId, index) => {
      positions.set(nodeId, {
        x: layer * HORIZONTAL_SPACING,
        y: startY + index * VERTICAL_SPACING,
      });
    });
  }

  return positions;
}

// ---------------------------------------------------------------------------
// Transform API data into React Flow nodes and edges
// ---------------------------------------------------------------------------

function buildFlowElements(
  data: DependencyGraphData,
  focusedId?: string
): { nodes: Node[]; edges: Edge[] } {
  const positions = computeLayout(data.nodes, data.edges);

  const nodes: Node[] = data.nodes.map((n) => {
    const pos = positions.get(n.id) ?? { x: 0, y: 0 };
    const isFocused = n.id === focusedId;

    return {
      id: n.id,
      position: pos,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      data: {
        label: n.name,
        nodeType: n.type,
        status: n.status,
        version: n.version,
        language: n.language,
      },
      style: {
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        padding: "12px 16px",
        borderRadius: "8px",
        border: isFocused
          ? "2px solid var(--color-primary)"
          : "1px solid var(--color-border)",
        boxShadow: isFocused
          ? "0 0 0 3px rgba(11, 99, 206, 0.25)"
          : "0 1px 3px rgba(0, 0, 0, 0.15)",
        background: "var(--color-surface)",
        color: "var(--color-text)",
        fontSize: "12px",
        display: "flex",
        flexDirection: "column" as const,
        gap: "4px",
      },
    };
  });

  const edges: Edge[] = data.edges.map((e, i) => ({
    id: `edge-${e.source}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
    type: "smoothstep",
    animated: true,
    style: {
      stroke: "var(--color-primary)",
      strokeWidth: 2,
      opacity: 0.6,
    },
  }));

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Custom node component
// ---------------------------------------------------------------------------

interface DepNodeData {
  label: string;
  nodeType: string;
  status?: string;
  version?: number;
  language?: string;
  [key: string]: unknown;
}

function DependencyNode({ data }: { data: DepNodeData }) {
  const isAutomation = data.nodeType === "automation";
  const badgeBg = isAutomation
    ? "bg-blue-500/20 text-blue-400"
    : "bg-green-500/20 text-green-400";

  return (
    <>
      <Handle type="target" position={Position.Left} />
      <div className="flex flex-col gap-1.5">
        <div className="font-semibold text-sm truncate text-[var(--color-text)]" title={data.label}>
          {data.label}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${badgeBg}`}>
            {isAutomation ? "automation" : "code block"}
          </span>
          {data.status && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] font-medium">
              {data.status}
            </span>
          )}
          {data.version != null && (
            <span className="text-[10px] text-[var(--color-text-muted)]">
              v{data.version}
            </span>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </>
  );
}

const nodeTypes = {
  default: DependencyNode,
};

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function DependencyGraphPage() {
  const { id: automationId } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dependency-graph", automationId ?? "all"],
    queryFn: () => {
      const params = automationId ? `?automation_id=${automationId}` : "";
      return api.get<DependencyGraphData>(`/automations/dependency-graph${params}`);
    },
  });

  const { initialNodes, initialEdges } = useMemo(() => {
    if (!data) return { initialNodes: [], initialEdges: [] };
    return {
      initialNodes: buildFlowElements(data, automationId).nodes,
      initialEdges: buildFlowElements(data, automationId).edges,
    };
  }, [data, automationId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync when data loads or automationId changes
  useEffect(() => {
    if (initialNodes.length > 0) {
      setNodes(initialNodes);
      setEdges(initialEdges);
    }
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  // Navigate on node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const nodeType = node.data?.nodeType;
      if (nodeType === "automation") {
        navigate(`/automations/${node.id}`);
      } else if (nodeType === "code_block") {
        navigate("/code-library");
      }
    },
    [navigate]
  );

  // Back link destination
  const backTo = automationId
    ? `/automations/${automationId}`
    : "/automations";

  return (
    <div className="flex flex-col -m-6" style={{ height: "100vh", width: "calc(100% + 3rem)" }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
        <Link
          to={backTo}
          className="flex items-center gap-1.5 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <div className="w-px h-5 bg-[var(--color-border)]" />
        <h1 className="text-lg font-semibold">Dependency Graph</h1>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center text-[var(--color-text-muted)]">
            Loading dependency graph...
          </div>
        ) : error ? (
          <div className="absolute inset-0 flex items-center justify-center text-red-500">
            Failed to load dependency graph. Please try again.
          </div>
        ) : nodes.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center text-[var(--color-text-muted)]">
            No dependencies found.
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              color="var(--color-surface-2)"
              gap={20}
              size={1}
            />
            <Controls
              className="[&>button]:bg-[var(--color-bg)] [&>button]:border-[var(--color-border)] [&>button]:text-[var(--color-text)] [&>button:hover]:bg-[var(--color-surface-2)]"
            />
            <MiniMap
              nodeColor={(node) => {
                const nodeType = node.data?.nodeType;
                if (nodeType === "automation") return "hsl(210 80% 70%)";
                if (nodeType === "code_block") return "hsl(140 70% 65%)";
                return "var(--color-surface-2)";
              }}
              maskColor="rgba(15, 23, 36, 0.7)"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: "6px",
              }}
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}
