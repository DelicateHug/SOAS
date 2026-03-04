/**
 * Hook to fetch the node type catalog from the backend.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NodeCatalogEntry, VP2Port, NodePropertyDef } from "../types/graph";

/** Shape returned by the backend node-catalog endpoint */
interface NodeCatalogResponse {
  nodes: BackendCatalogEntry[];
  categories: string[];
}

interface BackendCatalogEntry {
  type: string;
  name: string;
  category: string;
  color: string;
  description: string;
  icon: string | null;
  input_ports: BackendPortDef[];
  output_ports: BackendPortDef[];
  properties: BackendPropertyDef[];
}

interface BackendPortDef {
  name: string;
  type: string;
  description: string;
  required?: boolean;
  default_value?: unknown;
}

interface BackendPropertyDef {
  name: string;
  type: string;
  default_value?: unknown;
  ui_type?: string;
  description?: string;
  placeholder?: string;
}

/** Convert port name to a clean display label */
function portNameToLabel(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function mapPort(port: BackendPortDef): VP2Port {
  return {
    name: port.name,
    type: port.type as VP2Port["type"],
    label: portNameToLabel(port.name),
    inline_value: port.default_value as VP2Port["inline_value"],
    required: port.required ?? false,
  };
}

function mapProperty(prop: BackendPropertyDef): NodePropertyDef {
  const label = prop.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const base = {
    name: prop.name,
    label,
    default: prop.default_value,
    ...(prop.description ? { description: prop.description } : {}),
    ...(prop.placeholder ? { placeholder: prop.placeholder } : {}),
  };

  // Check for special UI type hints from the backend
  const uiTypeMap: Record<string, NodePropertyDef["type"]> = {
    automation_select: "automation_select",
    automation_input_select: "automation_input_select",
    soas_variable_select: "soas_variable_select",
    incident_variable_select: "incident_variable_select",
  };

  if (prop.ui_type && prop.ui_type in uiTypeMap) {
    return { ...base, type: uiTypeMap[prop.ui_type]! };
  }

  const typeMap: Record<string, NodePropertyDef["type"]> = {
    string: "string",
    integer: "number",
    float: "number",
    boolean: "boolean",
    list: "json",
    dict: "json",
    any: "string",
  };
  return { ...base, type: typeMap[prop.type] || "string" };
}

function mapEntry(entry: BackendCatalogEntry): NodeCatalogEntry {
  return {
    type: entry.type,
    label: entry.name,
    category: entry.category,
    description: entry.description,
    color: entry.color,
    inputs: entry.input_ports.map(mapPort),
    outputs: entry.output_ports.map(mapPort),
    properties: entry.properties.map(mapProperty),
  };
}

export function useNodeCatalog() {
  return useQuery({
    queryKey: ["graph-editor", "node-catalog"],
    queryFn: async () => {
      const res = await api.get<NodeCatalogResponse>("/graph-editor/node-catalog");
      return res.nodes.map(mapEntry);
    },
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
