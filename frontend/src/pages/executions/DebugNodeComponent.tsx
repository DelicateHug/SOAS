/**
 * Custom node component for the debug graph viewer.
 * Extends the standard node rendering with execution status overlays
 * (green = completed, red = error, gray = not reached).
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { PORT_TYPE_COLORS } from "@/components/graph-editor/utils/portColors";
import type { PortType, VP2Port } from "@/components/graph-editor/types/graph";

export interface NodeTraceExecution {
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  duration_ms: number;
  status: "completed" | "running" | "error";
  error?: string;
}

export interface NodeTraceEntry {
  type: string;
  label: string;
  executions: NodeTraceExecution[];
}

export interface DebugNodeData {
  type: string;
  label: string;
  color: string;
  inputs: VP2Port[];
  outputs: VP2Port[];
  /** Debug trace for this node, undefined if not reached */
  trace?: NodeTraceEntry;
  /** Callback when node is clicked for inspection */
  onInspect?: (nodeId: string) => void;
  nodeId: string;
  [key: string]: unknown;
}

type NodeStatus = "completed" | "error" | "not_reached";

function getNodeStatus(trace?: NodeTraceEntry): NodeStatus {
  if (!trace || trace.executions.length === 0) return "not_reached";
  const last = trace.executions[trace.executions.length - 1];
  if (!last || last.status === "completed") return "completed";
  return "error";
}

const STATUS_STYLES: Record<NodeStatus, { border: string; shadow: string; opacity: string }> = {
  completed: {
    border: "border-green-500",
    shadow: "shadow-green-500/30 shadow-lg",
    opacity: "",
  },
  error: {
    border: "border-red-500",
    shadow: "shadow-red-500/30 shadow-lg",
    opacity: "",
  },
  not_reached: {
    border: "border-gray-600",
    shadow: "",
    opacity: "opacity-40",
  },
};

function getPortColor(type: string): string {
  return PORT_TYPE_COLORS[type as PortType] || PORT_TYPE_COLORS.ANY;
}

function DebugNodeInner({ data, id }: NodeProps) {
  const nodeData = data as unknown as DebugNodeData;
  const { label, color, inputs, outputs, trace, onInspect, nodeId } = nodeData;
  const status = getNodeStatus(trace);
  const style = STATUS_STYLES[status];
  const execCount = trace?.executions.length ?? 0;
  const maxPorts = Math.max(inputs.length, outputs.length);

  return (
    <div
      className={`
        rounded-lg border-2 transition-all cursor-pointer
        bg-[#1a1a2e]
        ${style.border} ${style.shadow} ${style.opacity}
      `}
      style={{ minWidth: 160 }}
      onClick={() => onInspect?.(nodeId || id)}
    >
      {/* Node header with status indicator */}
      <div
        className="px-3 py-1.5 rounded-t-[5px] text-white text-xs font-semibold tracking-wide flex items-center justify-between gap-2"
        style={{ backgroundColor: color }}
      >
        <span className="truncate">{label}</span>
        <div className="flex items-center gap-1 shrink-0">
          {execCount > 1 && (
            <span className="text-[9px] bg-black/30 px-1 rounded">
              x{execCount}
            </span>
          )}
          {status === "completed" && (
            <span className="w-2.5 h-2.5 rounded-full bg-green-400 border border-green-300" />
          )}
          {status === "error" && (
            <span className="w-2.5 h-2.5 rounded-full bg-red-400 border border-red-300" />
          )}
          {status === "not_reached" && (
            <span className="w-2.5 h-2.5 rounded-full bg-gray-500 border border-gray-400" />
          )}
        </div>
      </div>

      {/* Port rows */}
      {maxPorts > 0 && (
        <div className="py-1.5">
          {Array.from({ length: maxPorts }).map((_, i) => {
            const input = inputs[i];
            const output = outputs[i];

            return (
              <div
                key={`row-${i}`}
                className="relative flex items-center justify-between"
                style={{ minHeight: 24, padding: "2px 10px" }}
              >
                {input ? (
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Handle
                      type="target"
                      position={Position.Left}
                      id={input.name}
                      style={{
                        position: "absolute",
                        left: -5,
                        top: "50%",
                        transform: input.type === "FLOW"
                          ? "translateY(-50%) rotate(45deg)"
                          : "translateY(-50%)",
                        background: getPortColor(input.type),
                        width: input.type === "FLOW" ? 10 : 8,
                        height: input.type === "FLOW" ? 10 : 8,
                        borderRadius: input.type === "FLOW" ? 2 : "50%",
                        border: `1.5px solid ${getPortColor(input.type)}`,
                      }}
                    />
                    <span className="text-[10px] text-gray-400 truncate">
                      {input.label || input.name}
                    </span>
                  </div>
                ) : (
                  <span />
                )}

                {output ? (
                  <div className="flex items-center gap-1.5 min-w-0 ml-auto">
                    <span className="text-[10px] text-gray-400 truncate text-right">
                      {output.label || output.name}
                    </span>
                    <Handle
                      type="source"
                      position={Position.Right}
                      id={output.name}
                      style={{
                        position: "absolute",
                        right: -5,
                        top: "50%",
                        transform: output.type === "FLOW"
                          ? "translateY(-50%) rotate(45deg)"
                          : "translateY(-50%)",
                        background: getPortColor(output.type),
                        width: output.type === "FLOW" ? 10 : 8,
                        height: output.type === "FLOW" ? 10 : 8,
                        borderRadius: output.type === "FLOW" ? 2 : "50%",
                        border: `1.5px solid ${getPortColor(output.type)}`,
                      }}
                    />
                  </div>
                ) : (
                  <span />
                )}
              </div>
            );
          })}
        </div>
      )}

      {maxPorts === 0 && (
        <div className="px-3 py-1.5">
          <span className="text-[10px] text-gray-500 italic">No ports</span>
        </div>
      )}
    </div>
  );
}

export const DebugNodeComponent = memo(DebugNodeInner);
