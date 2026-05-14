/**
 * Live preview of how the code block will look as a node on the graph canvas.
 * Mirrors the exact visual style of CustomNodeComponent.
 */

import type { PortDefinition } from "./PortBuilder";

/** Port type color map — matches portColors.ts exactly */
const PORT_COLORS: Record<string, string> = {
  FLOW: "#ffffff",
  STRING: "#22c55e",
  INTEGER: "#3b82f6",
  FLOAT: "#6366f1",
  BOOLEAN: "#f59e0b",
  LIST: "#8b5cf6",
  DICT: "#a855f7",
  OBJECT: "#64748b",
  ANY: "#94a3b8",
};

interface PortDot {
  name: string;
  type: string;
}

interface NodePreviewProps {
  name: string;
  inputPorts: PortDefinition[];
  outputPorts: PortDefinition[];
}

export function NodePreview({ name, inputPorts, outputPorts }: NodePreviewProps) {
  // Build full port lists including FLOW ports
  const allInputs: PortDot[] = [
    { name: "exec_in", type: "FLOW" },
    ...inputPorts,
  ];
  const allOutputs: PortDot[] = [
    { name: "exec_out", type: "FLOW" },
    ...outputPorts,
  ];

  const maxRows = Math.max(allInputs.length, allOutputs.length);
  const displayName = name || "Untitled Block";

  return (
    <div>
      <label className="block text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-2">
        Preview
      </label>
      <div className="flex justify-center py-2">
        <div
          className="rounded-lg shadow-md border border-[#2a2a3e] bg-[#1a1a2e]"
          style={{ minWidth: 170, maxWidth: 240 }}
        >
          {/* Node header — green for code blocks */}
          <div
            className="px-3 py-1.5 rounded-t-[7px] text-white text-xs font-semibold tracking-wide truncate"
            style={{ backgroundColor: "#4CAF50" }}
          >
            {displayName}
          </div>

          {/* Port rows */}
          {maxRows > 0 && (
            <div className="py-1.5">
              {Array.from({ length: maxRows }).map((_, i) => {
                const input = allInputs[i];
                const output = allOutputs[i];

                return (
                  <div
                    key={i}
                    className="relative flex items-center justify-between"
                    style={{ minHeight: 22, padding: "2px 10px" }}
                  >
                    {/* Input port */}
                    {input ? (
                      <div className="flex items-center gap-1.5 min-w-0">
                        {/* Port dot */}
                        <div
                          className="shrink-0"
                          style={{
                            width: input.type === "FLOW" ? 9 : 7,
                            height: input.type === "FLOW" ? 9 : 7,
                            borderRadius: input.type === "FLOW" ? 2 : "50%",
                            transform: input.type === "FLOW" ? "rotate(45deg)" : undefined,
                            backgroundColor: PORT_COLORS[input.type] || PORT_COLORS.ANY,
                          }}
                        />
                        <span className="text-[10px] text-gray-400 truncate">
                          {input.name}
                        </span>
                      </div>
                    ) : (
                      <span />
                    )}

                    {/* Output port */}
                    {output ? (
                      <div className="flex items-center gap-1.5 min-w-0 ml-auto">
                        <span className="text-[10px] text-gray-400 truncate text-right">
                          {output.name}
                        </span>
                        <div
                          className="shrink-0"
                          style={{
                            width: output.type === "FLOW" ? 9 : 7,
                            height: output.type === "FLOW" ? 9 : 7,
                            borderRadius: output.type === "FLOW" ? 2 : "50%",
                            transform: output.type === "FLOW" ? "rotate(45deg)" : undefined,
                            backgroundColor: PORT_COLORS[output.type] || PORT_COLORS.ANY,
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
        </div>
      </div>
    </div>
  );
}
