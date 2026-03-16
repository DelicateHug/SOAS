/**
 * TypeScript types for the VisualPython2 graph editor.
 * These mirror the VP2 JSON format used by the backend.
 */

/** All supported port data types (must match backend PortType enum names) */
export type PortType =
  | "FLOW"
  | "STRING"
  | "INTEGER"
  | "FLOAT"
  | "BOOLEAN"
  | "LIST"
  | "DICT"
  | "OBJECT"
  | "ANY";

/** A connection between two node ports in the VP2 format */
export interface VP2Connection {
  id: string;
  source_node_id: string;
  source_port: string;
  target_node_id: string;
  target_port: string;
}

/** A port definition on a node */
export interface VP2Port {
  name: string;
  type: PortType;
  label?: string;
  /** For input ports: an optional inline/default value */
  inline_value?: string | number | boolean | null;
  /** Whether this input port is required (for dynamic automation inputs) */
  required?: boolean;
}

/** A node in the VP2 graph format */
export interface VP2Node {
  id: string;
  type: string;
  label: string;
  position: { x: number; y: number };
  inputs: VP2Port[];
  outputs: VP2Port[];
  properties: Record<string, unknown>;
}

/** The complete VP2 graph data format (stored as JSON) */
export interface VP2GraphData {
  id: string;
  name: string;
  description: string;
  version: number;
  trigger_tags: string[];
  nodes: VP2Node[];
  connections: VP2Connection[];
}

/** A node type entry from the server's catalog */
export interface NodeCatalogEntry {
  type: string;
  label: string;
  category: string;
  description: string;
  color: string;
  doc_url?: string | null;
  inputs: VP2Port[];
  outputs: VP2Port[];
  properties: NodePropertyDef[];
}

/** Definition of a configurable property on a node type */
export interface NodePropertyDef {
  name: string;
  label: string;
  type: "string" | "number" | "boolean" | "code" | "select" | "json" | "automation_select" | "automation_input_select" | "soas_variable_select" | "incident_variable_select" | "user_secret_select" | "team_variable_select";
  default?: unknown;
  options?: Array<string | { value: string; label: string }>;
  description?: string;
  placeholder?: string;
  /** Hide this property unless the referenced property has one of the listed values */
  visible_when?: Record<string, string[]>;
}

/** Validation error for a single node */
export interface ValidationError {
  nodeId: string;
  message: string;
}

/** Compilation warning */
export interface CompilationWarning {
  nodeId?: string;
  message: string;
}
