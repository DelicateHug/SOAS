/**
 * Static visual preview of a graph node for wiki pages.
 * Replicates the look of CustomNodeComponent without React Flow dependencies.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NodeCatalogEntry, VP2Port } from "@/components/graph-editor/types/graph";

const PORT_TYPE_COLORS: Record<string, string> = {
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

function portNameToLabel(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function PortDot({ type }: { type: string }) {
  const color = PORT_TYPE_COLORS[type] || PORT_TYPE_COLORS.ANY;
  const isFlow = type === "FLOW";
  return (
    <span
      style={{
        display: "inline-block",
        width: isFlow ? 10 : 8,
        height: isFlow ? 10 : 8,
        borderRadius: isFlow ? 2 : "50%",
        transform: isFlow ? "rotate(45deg)" : undefined,
        background: color,
        border: `1.5px solid ${color}`,
        flexShrink: 0,
      }}
    />
  );
}

function PortTypeBadge({ type }: { type: string }) {
  const color = PORT_TYPE_COLORS[type] || PORT_TYPE_COLORS.ANY;
  return (
    <span
      className="text-[9px] px-1 py-px rounded font-mono"
      style={{ color, backgroundColor: `${color}18` }}
    >
      {type}
    </span>
  );
}

interface BackendCatalogEntry {
  type: string;
  name: string;
  category: string;
  color: string;
  description: string;
  icon: string | null;
  doc_url: string | null;
  input_ports: { name: string; type: string; description: string; required?: boolean; default_value?: unknown }[];
  output_ports: { name: string; type: string; description: string }[];
  properties: { name: string; type: string; default_value?: unknown; description?: string; ui_type?: string }[];
}

function mapEntry(entry: BackendCatalogEntry): NodeCatalogEntry {
  return {
    type: entry.type,
    label: entry.name,
    category: entry.category,
    description: entry.description,
    color: entry.color,
    doc_url: entry.doc_url,
    inputs: entry.input_ports.map((p) => ({
      name: p.name,
      type: p.type as VP2Port["type"],
      label: portNameToLabel(p.name),
      required: p.required ?? false,
    })),
    outputs: entry.output_ports.map((p) => ({
      name: p.name,
      type: p.type as VP2Port["type"],
      label: portNameToLabel(p.name),
    })),
    properties: entry.properties.map((p) => ({
      name: p.name,
      label: portNameToLabel(p.name),
      type: "string" as const,
      description: p.description,
    })),
  };
}

export function NodePreview({ nodeType, compact }: { nodeType: string; compact?: boolean }) {
  const { data: node, isLoading } = useQuery({
    queryKey: ["node-catalog-entry", nodeType],
    queryFn: async () => {
      const res = await api.get<{ nodes: BackendCatalogEntry[]; categories: string[] }>(
        "/graph-editor/node-catalog"
      );
      const entry = res.nodes.find((n) => n.type === nodeType);
      return entry ? mapEntry(entry) : null;
    },
    staleTime: Infinity,
  });

  if (isLoading || !node) return null;

  const maxPorts = Math.max(node.inputs.length, node.outputs.length);

  const nodeVisual = (
    <div
      className="rounded-lg shadow-md border border-[#2a2a3e] bg-[#1a1a2e]"
      style={{ minWidth: compact ? 220 : 180 }}
    >
      {/* Header */}
      <div
        className={`rounded-t-[7px] text-white font-semibold tracking-wide ${compact ? "px-4 py-2 text-sm" : "px-3 py-1.5 text-xs"}`}
        style={{ backgroundColor: node.color }}
      >
        {node.label}
      </div>

      {/* Port rows */}
      {maxPorts > 0 && (
        <div className={compact ? "py-2" : "py-1.5"}>
          {Array.from({ length: maxPorts }).map((_, i) => {
            const input = node.inputs[i];
            const output = node.outputs[i];
            return (
              <div
                key={i}
                className="relative flex items-center justify-between"
                style={{ minHeight: compact ? 28 : 24, padding: compact ? "2px 14px" : "2px 10px" }}
              >
                {input ? (
                  <div className="flex items-center gap-1.5 min-w-0">
                    <PortDot type={input.type} />
                    <span className={`text-gray-400 truncate ${compact ? "text-xs" : "text-[10px]"}`}>
                      {input.label || input.name}
                    </span>
                  </div>
                ) : (
                  <span />
                )}
                {output ? (
                  <div className="flex items-center gap-1.5 min-w-0 ml-auto">
                    <span className={`text-gray-400 truncate text-right ${compact ? "text-xs" : "text-[10px]"}`}>
                      {output.label || output.name}
                    </span>
                    <PortDot type={output.type} />
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

  if (compact) return nodeVisual;

  return (
    <div className="flex items-start gap-6 p-4 mb-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="shrink-0">{nodeVisual}</div>

      {/* Node info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span
            className="text-xs font-medium px-2 py-0.5 rounded"
            style={{ backgroundColor: `${node.color}25`, color: node.color }}
          >
            {node.category}
          </span>
          <span className="text-xs text-[var(--color-text-muted)] font-mono">{node.type}</span>
        </div>
        {node.description && (
          <p className="text-sm text-[var(--color-text-muted)] mb-3">{node.description}</p>
        )}

        {/* Ports summary */}
        <div className="grid grid-cols-2 gap-4">
          {node.inputs.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1.5">
                Inputs
              </p>
              <div className="space-y-1">
                {node.inputs.map((p) => (
                  <div key={p.name} className="flex items-center gap-1.5 text-xs">
                    <PortDot type={p.type} />
                    <span className="text-[var(--color-text)]">{p.label || p.name}</span>
                    <PortTypeBadge type={p.type} />
                  </div>
                ))}
              </div>
            </div>
          )}
          {node.outputs.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1.5">
                Outputs
              </p>
              <div className="space-y-1">
                {node.outputs.map((p) => (
                  <div key={p.name} className="flex items-center gap-1.5 text-xs">
                    <PortDot type={p.type} />
                    <span className="text-[var(--color-text)]">{p.label || p.name}</span>
                    <PortTypeBadge type={p.type} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
