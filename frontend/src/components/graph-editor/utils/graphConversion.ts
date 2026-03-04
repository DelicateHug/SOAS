/**
 * Conversion utilities between VP2 graph data format and React Flow format.
 */

import type { Node, Edge } from "@xyflow/react";
import type {
  VP2GraphData,
  VP2Node,
  VP2Connection,
  VP2Port,
  NodeCatalogEntry,
  PortType,
} from "../types/graph";
import { PORT_TYPE_COLORS } from "./portColors";

/** Data stored on React Flow nodes */
export interface CustomNodeData {
  type: string;
  label: string;
  color: string;
  inputs: VP2Port[];
  outputs: VP2Port[];
  properties: Record<string, unknown>;
  catalogEntry?: NodeCatalogEntry;
  [key: string]: unknown;
}

/** Custom type alias for our nodes */
export type GraphNode = Node<CustomNodeData>;

/** Check whether a connection is a FLOW (execution) connection */
export function isFlowConnection(
  sourcePort: string,
  nodes: Node<CustomNodeData>[]
): boolean {
  for (const node of nodes) {
    const data = node.data as CustomNodeData;
    const output = data.outputs.find((p) => p.name === sourcePort);
    if (output) return output.type === "FLOW";
  }
  return false;
}

/** Get the port type from a source node's output port */
function getSourcePortType(
  sourceNodeId: string,
  sourcePort: string,
  nodes: VP2Node[],
  catalog: NodeCatalogEntry[]
): PortType {
  const node = nodes.find((n) => n.id === sourceNodeId);
  if (node) {
    const port = node.outputs.find((p) => p.name === sourcePort);
    if (port) return port.type;
  }
  // Fallback: check catalog for the node type
  if (node) {
    const entry = catalog.find((c) => c.type === node.type);
    if (entry) {
      const port = entry.outputs.find((p) => p.name === sourcePort);
      if (port) return port.type;
    }
  }
  return "ANY";
}

/**
 * Convert VP2 graph data + catalog to React Flow nodes and edges.
 */
export function vp2ToReactFlow(
  graphData: VP2GraphData,
  catalog: NodeCatalogEntry[]
): { nodes: Node<CustomNodeData>[]; edges: Edge[] } {
  const nodes: Node<CustomNodeData>[] = graphData.nodes.map((vp2Node) => {
    const catalogEntry = catalog.find((c) => c.type === vp2Node.type);

    // Merge saved inputs with catalog to pick up `required` field
    let inputs: VP2Port[] = vp2Node.inputs.length > 0
      ? vp2Node.inputs.map((saved) => {
          const catPort = catalogEntry?.inputs.find((c) => c.name === saved.name);
          return {
            ...saved,
            required: saved.required ?? catPort?.required ?? false,
          };
        })
      : catalogEntry?.inputs || [];
    let outputs = vp2Node.outputs.length > 0
      ? vp2Node.outputs
      : catalogEntry?.outputs || [];

    // For run_automation nodes with _input_defs, rebuild dynamic ports
    if (
      vp2Node.type === "run_automation" &&
      Array.isArray(vp2Node.properties._input_defs) &&
      (vp2Node.properties._input_defs as Array<Record<string, unknown>>).length > 0
    ) {
      const flowInputs = inputs.filter((p) => p.type === "FLOW");
      const defs = vp2Node.properties._input_defs as Array<{
        name: string;
        type: string;
        required: boolean;
        default_value: unknown;
        description: string;
      }>;
      const dynamicInputs: VP2Port[] = defs.map((def) => {
        // Try to restore the saved inline_value from the original inputs
        const savedPort = vp2Node.inputs.find((p) => p.name === def.name);
        return {
          name: def.name,
          type: (def.type || "ANY") as PortType,
          label: def.name,
          inline_value: savedPort?.inline_value ?? (def.default_value as VP2Port["inline_value"]) ?? null,
          required: def.required,
        };
      });
      inputs = [...flowInputs, ...dynamicInputs];
    }

    // For start nodes with _input_defs, rebuild dynamic output ports
    if (
      vp2Node.type === "start" &&
      Array.isArray(vp2Node.properties._input_defs) &&
      (vp2Node.properties._input_defs as Array<Record<string, unknown>>).length > 0
    ) {
      const flowOutputs = outputs.filter((p) => p.type === "FLOW");
      const defs = vp2Node.properties._input_defs as Array<{
        name: string;
        type: string;
        required: boolean;
        default_value: unknown;
        description: string;
      }>;
      const dynamicOutputs: VP2Port[] = defs.map((def) => ({
        name: def.name,
        type: (def.type || "ANY") as PortType,
        label: def.name,
      }));
      outputs = [...flowOutputs, ...dynamicOutputs];
    }

    // Use automation name as label for run_automation nodes when available
    const displayLabel =
      vp2Node.type === "run_automation" &&
      typeof vp2Node.properties.automation_name === "string" &&
      vp2Node.properties.automation_name
        ? vp2Node.properties.automation_name
        : vp2Node.label;

    return {
      id: vp2Node.id,
      type: "custom",
      position: vp2Node.position,
      data: {
        type: vp2Node.type,
        label: displayLabel,
        color: catalogEntry?.color || "#6b7280",
        inputs,
        outputs,
        properties: vp2Node.properties,
        catalogEntry,
      },
    };
  });

  const edges: Edge[] = graphData.connections.map((conn) => {
    const portType = getSourcePortType(
      conn.source_node_id,
      conn.source_port,
      graphData.nodes,
      catalog
    );
    const isFlow = portType === "FLOW";

    return {
      id: conn.id,
      source: conn.source_node_id,
      target: conn.target_node_id,
      sourceHandle: conn.source_port,
      targetHandle: conn.target_port,
      type: isFlow ? "flowEdge" : "dataEdge",
      data: {
        portType,
        color: PORT_TYPE_COLORS[portType] || PORT_TYPE_COLORS.ANY,
      },
    };
  });

  return { nodes, edges };
}

/**
 * Convert React Flow nodes/edges back to VP2 graph data format.
 */
export function reactFlowToVP2(
  nodes: Node<CustomNodeData>[],
  edges: Edge[],
  metadata: { name: string; description: string; triggerTags: string[] },
  graphId: string
): VP2GraphData {
  const vp2Nodes: VP2Node[] = nodes.map((node) => {
    const data = node.data as CustomNodeData;
    return {
      id: node.id,
      type: data.type,
      label: data.label,
      position: { x: node.position.x, y: node.position.y },
      inputs: data.inputs,
      outputs: data.outputs,
      properties: data.properties,
    };
  });

  const vp2Connections: VP2Connection[] = edges.map((edge) => ({
    id: edge.id,
    source_node_id: edge.source,
    source_port: edge.sourceHandle || "",
    target_node_id: edge.target,
    target_port: edge.targetHandle || "",
  }));

  return {
    id: graphId,
    name: metadata.name,
    description: metadata.description,
    version: 1,
    trigger_tags: metadata.triggerTags,
    nodes: vp2Nodes,
    connections: vp2Connections,
  };
}

/**
 * Convert frontend VP2GraphData to the backend-expected format.
 *
 * Backend GraphDataSchema expects:
 *  - metadata wrapper (name, description, trigger_tags)
 *  - nodes with: name (not label), input_ports (not inputs), output_ports (not outputs)
 *  - connections with: source_port_name (not source_port), target_port_name (not target_port)
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function toBackendFormat(data: VP2GraphData): Record<string, any> {
  return {
    id: data.id,
    metadata: {
      name: data.name,
      description: data.description,
      trigger_tags: data.trigger_tags,
      version: "1.0.0",
    },
    nodes: data.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      name: node.label,
      position: node.position,
      input_ports: node.inputs.map((port) => {
        // Use port inline_value, falling back to matching node property
        const value = port.inline_value ?? node.properties[port.name] ?? null;
        return {
          name: port.name,
          type: port.type,
          description: port.label || "",
          inline_value: value,
          default_value: value,
        };
      }),
      output_ports: node.outputs.map((port) => ({
        name: port.name,
        type: port.type,
        description: port.label || "",
      })),
      properties: node.properties,
    })),
    connections: data.connections.map((conn) => ({
      source_node_id: conn.source_node_id,
      source_port_name: conn.source_port,
      target_node_id: conn.target_node_id,
      target_port_name: conn.target_port,
    })),
  };
}

/**
 * Convert backend graph data to frontend VP2GraphData format.
 * Handles both frontend format (label, inputs, outputs, source_port)
 * and backend format (name, input_ports, output_ports, source_port_name).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function fromBackendFormat(data: Record<string, any>): VP2GraphData {
  const metadata = data.metadata || {};
  const name = data.name || metadata.name || "Untitled";
  const description = data.description || metadata.description || "";
  const triggerTags = data.trigger_tags || metadata.trigger_tags || [];

  return {
    id: data.id || "",
    name,
    description,
    version: 1,
    trigger_tags: triggerTags,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    nodes: (data.nodes || []).map((node: any) => ({
      id: node.id,
      type: node.type,
      label: node.label || node.name || node.type,
      position: node.position || { x: 0, y: 0 },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      inputs: (node.inputs || node.input_ports || []).map((port: any) => ({
        name: port.name,
        type: port.type,
        label: port.label || port.description || "",
        inline_value: port.inline_value ?? port.default_value ?? null,
        ...(port.required != null ? { required: port.required } : {}),
      })),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      outputs: (node.outputs || node.output_ports || []).map((port: any) => ({
        name: port.name,
        type: port.type,
        label: port.label || port.description || "",
      })),
      properties: node.properties || {},
    })),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    connections: (data.connections || []).map((conn: any) => ({
      id: conn.id || `conn_${Math.random().toString(36).substring(2, 9)}`,
      source_node_id: conn.source_node_id,
      source_port: conn.source_port || conn.source_port_name,
      target_node_id: conn.target_node_id,
      target_port: conn.target_port || conn.target_port_name,
    })),
  };
}
