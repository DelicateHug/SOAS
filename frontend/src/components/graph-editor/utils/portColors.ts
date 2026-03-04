/**
 * Color mapping for each port data type.
 * Used for port handles and data edges.
 * Keys match backend PortType enum names exactly.
 */

import type { PortType } from "../types/graph";

export const PORT_TYPE_COLORS: Record<PortType, string> = {
  FLOW: "#ffffff",
  STRING: "#22c55e",     // green-500
  INTEGER: "#3b82f6",    // blue-500
  FLOAT: "#6366f1",      // indigo-500
  BOOLEAN: "#f59e0b",    // amber-500
  LIST: "#8b5cf6",       // violet-500
  DICT: "#a855f7",       // purple-500
  OBJECT: "#64748b",     // slate-500
  ANY: "#94a3b8",        // slate-400
};
