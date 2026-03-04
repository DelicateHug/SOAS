/**
 * Read-only debug graph viewer for execution history.
 * Renders the automation graph with per-node execution status overlays.
 * Click a node to inspect its inputs/outputs.
 */

import { useMemo, useState, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useNodeCatalog } from "@/components/graph-editor/hooks/useNodeCatalog";
import { fromBackendFormat, vp2ToReactFlow } from "@/components/graph-editor/utils/graphConversion";
import { FlowEdge } from "@/components/graph-editor/edges/FlowEdge";
import { DataEdge } from "@/components/graph-editor/edges/DataEdge";
import {
  DebugNodeComponent,
  type DebugNodeData,
  type NodeTraceEntry,
  type NodeTraceExecution,
} from "./DebugNodeComponent";

interface DebugGraphProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  graphData: Record<string, any>;
  nodeTrace: Record<string, NodeTraceEntry>;
}

const nodeTypes = { debugNode: DebugNodeComponent };
const edgeTypes = { flowEdge: FlowEdge, dataEdge: DataEdge };

export function DebugGraph({ graphData, nodeTrace }: DebugGraphProps) {
  const { data: catalog } = useNodeCatalog();
  const [inspectedNodeId, setInspectedNodeId] = useState<string | null>(null);

  const handleInspect = useCallback((nodeId: string) => {
    setInspectedNodeId((prev) => (prev === nodeId ? null : nodeId));
  }, []);

  // Convert graph data to React Flow format with debug overlays
  const { nodes, edges } = useMemo(() => {
    if (!catalog) return { nodes: [], edges: [] };

    const vp2Data = fromBackendFormat(graphData);
    const { nodes: rfNodes, edges: rfEdges } = vp2ToReactFlow(vp2Data, catalog);

    // Re-map nodes to use debugNode type with trace data
    const debugNodes: Node<DebugNodeData>[] = rfNodes.map((node) => {
      const data = node.data as unknown as DebugNodeData;
      return {
        ...node,
        type: "debugNode",
        data: {
          ...data,
          trace: nodeTrace[node.id],
          onInspect: handleInspect,
          nodeId: node.id,
        },
        draggable: false,
        selectable: false,
        connectable: false,
      };
    });

    return { nodes: debugNodes, edges: rfEdges };
  }, [catalog, graphData, nodeTrace, handleInspect]);

  // Get the inspected node's trace data
  const inspectedTrace = inspectedNodeId ? nodeTrace[inspectedNodeId] : null;
  const inspectedNode = inspectedNodeId
    ? nodes.find((n) => n.id === inspectedNodeId)
    : null;

  if (!catalog) {
    return <div className="text-sm text-[hsl(var(--muted-foreground))] py-4">Loading graph...</div>;
  }

  return (
    <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-[hsl(var(--border))] flex items-center justify-between">
        <h2 className="font-semibold text-sm">Debug Graph</h2>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400" /> Completed
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400" /> Error
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-gray-500" /> Not Reached
          </span>
        </div>
      </div>

      <div className="flex" style={{ height: 450 }}>
        {/* Graph canvas */}
        <div className={inspectedTrace ? "w-2/3" : "w-full"} style={{ height: "100%" }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            panOnScroll
            zoomOnScroll
            minZoom={0.2}
            maxZoom={2}
          >
            <Background color="#333" gap={20} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>

        {/* Inspection panel */}
        {inspectedTrace && inspectedNode && (
          <NodeInspector
            nodeId={inspectedNodeId!}
            trace={inspectedTrace}
            label={inspectedNode.data.label}
            nodeType={inspectedNode.data.type}
            onClose={() => setInspectedNodeId(null)}
          />
        )}
      </div>
    </div>
  );
}

/** Side panel for inspecting a node's debug data */
function NodeInspector({
  nodeId,
  trace,
  label,
  nodeType,
  onClose,
}: {
  nodeId: string;
  trace: NodeTraceEntry;
  label: string;
  nodeType: string;
  onClose: () => void;
}) {
  const [selectedExec, setSelectedExec] = useState(0);
  const execCount = trace.executions.length;
  const exec: NodeTraceExecution | undefined =
    trace.executions[Math.min(selectedExec, execCount - 1)];

  const status = exec?.status === "completed" ? "completed" : "error";

  return (
    <div className="w-1/3 border-l border-[hsl(var(--border))] overflow-y-auto bg-[hsl(var(--card))]">
      <div className="px-3 py-2 border-b border-[hsl(var(--border))] flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold">{label}</p>
          <p className="text-[10px] text-[hsl(var(--muted-foreground))]">
            {nodeType} &middot; {nodeId.slice(0, 8)}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] px-1"
        >
          X
        </button>
      </div>

      {/* Execution selector for loop nodes */}
      {execCount > 1 && (
        <div className="px-3 py-2 border-b border-[hsl(var(--border))] flex items-center gap-2">
          <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
            Iteration:
          </span>
          <select
            value={selectedExec}
            onChange={(e) => setSelectedExec(Number(e.target.value))}
            className="text-xs bg-[hsl(var(--background))] border border-[hsl(var(--border))] rounded px-1 py-0.5"
          >
            {Array.from({ length: execCount }).map((_, i) => (
              <option key={i} value={i}>
                #{i + 1}
                {i === execCount - 1 ? " (latest)" : ""}
              </option>
            ))}
          </select>
          <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
            of {execCount}
          </span>
        </div>
      )}

      {exec ? (
        <div className="px-3 py-2 space-y-3">
          {/* Status + duration */}
          <div className="flex items-center gap-2">
            <span
              className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                status === "completed"
                  ? "bg-green-900/40 text-green-400"
                  : "bg-red-900/40 text-red-400"
              }`}
            >
              {status}
            </span>
            {exec.duration_ms != null && (
              <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                {exec.duration_ms < 1
                  ? `${(exec.duration_ms * 1000).toFixed(0)}us`
                  : exec.duration_ms < 1000
                    ? `${exec.duration_ms.toFixed(1)}ms`
                    : `${(exec.duration_ms / 1000).toFixed(2)}s`}
              </span>
            )}
          </div>

          {/* Error */}
          {exec.error && (
            <div className="bg-red-900/20 border border-red-800/30 rounded p-2">
              <p className="text-[10px] font-medium text-red-400 mb-1">Error</p>
              <pre className="text-[10px] text-red-300 whitespace-pre-wrap break-all font-mono">
                {exec.error}
              </pre>
            </div>
          )}

          {/* Inputs */}
          <div>
            <p className="text-[10px] font-medium text-[hsl(var(--muted-foreground))] mb-1">
              Inputs
            </p>
            {Object.keys(exec.inputs).length > 0 ? (
              <div className="space-y-1">
                {Object.entries(exec.inputs).map(([port, value]) => (
                  <div
                    key={port}
                    className="bg-[hsl(var(--background))] rounded p-1.5 border border-[hsl(var(--border))]"
                  >
                    <p className="text-[10px] font-medium text-blue-400">{port}</p>
                    <pre className="text-[10px] text-[hsl(var(--foreground))] whitespace-pre-wrap break-all font-mono mt-0.5">
                      {value}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-[hsl(var(--muted-foreground))] italic">
                No inputs
              </p>
            )}
          </div>

          {/* Outputs */}
          <div>
            <p className="text-[10px] font-medium text-[hsl(var(--muted-foreground))] mb-1">
              Outputs
            </p>
            {Object.keys(exec.outputs).length > 0 ? (
              <div className="space-y-1">
                {Object.entries(exec.outputs).map(([port, value]) => (
                  <div
                    key={port}
                    className="bg-[hsl(var(--background))] rounded p-1.5 border border-[hsl(var(--border))]"
                  >
                    <p className="text-[10px] font-medium text-green-400">{port}</p>
                    <pre className="text-[10px] text-[hsl(var(--foreground))] whitespace-pre-wrap break-all font-mono mt-0.5">
                      {value}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-[hsl(var(--muted-foreground))] italic">
                No outputs
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="px-3 py-4 text-center">
          <p className="text-[10px] text-[hsl(var(--muted-foreground))]">
            Node was not reached during execution
          </p>
        </div>
      )}
    </div>
  );
}
