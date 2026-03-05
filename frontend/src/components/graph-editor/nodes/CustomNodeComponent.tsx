/**
 * Custom node component for the React Flow graph editor.
 * Renders a compact node with colored header bar, and properly positioned
 * input/output port handles that align with their labels.
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { CustomNodeData } from "../utils/graphConversion";
import { PORT_TYPE_COLORS } from "../utils/portColors";
import type { PortType } from "../types/graph";

function getPortColor(type: string): string {
  return PORT_TYPE_COLORS[type as PortType] || PORT_TYPE_COLORS.ANY;
}

function CustomNodeComponentInner({ data, selected }: NodeProps) {
  const nodeData = data as unknown as CustomNodeData;
  const { label, color, inputs, outputs } = nodeData;

  const maxPorts = Math.max(inputs.length, outputs.length);

  return (
    <div
      className={`
        rounded-lg shadow-md border transition-[border-color,box-shadow] duration-150
        bg-[#1a1a2e]
        ${selected ? "shadow-lg shadow-blue-500/20 border-blue-500" : "border-[#2a2a3e]"}
      `}
      style={{ minWidth: 160 }}
    >
      {/* Node header */}
      <div
        className="px-3 py-1.5 rounded-t-[7px] text-white text-xs font-semibold tracking-wide"
        style={{ backgroundColor: color }}
      >
        {label}
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
                {/* Input port (left side) */}
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

                {/* Output port (right side) */}
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

      {/* Bottom padding for nodes with no ports */}
      {maxPorts === 0 && (
        <div className="px-3 py-1.5">
          <span className="text-[10px] text-gray-500 italic">No ports</span>
        </div>
      )}
    </div>
  );
}

export const CustomNodeComponent = memo(CustomNodeComponentInner);
