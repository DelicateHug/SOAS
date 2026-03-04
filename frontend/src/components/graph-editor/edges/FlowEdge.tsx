/**
 * Custom edge for FLOW (execution) connections.
 * Solid white line with subtle glow.
 */

import { memo } from "react";
import { BezierEdge, type EdgeProps } from "@xyflow/react";

function FlowEdgeInner(props: EdgeProps) {
  const selected = props.selected;
  return (
    <>
      {/* Glow background */}
      <BezierEdge
        {...props}
        style={{
          stroke: selected ? "rgba(59, 130, 246, 0.3)" : "rgba(255, 255, 255, 0.1)",
          strokeWidth: selected ? 8 : 6,
        }}
      />
      {/* Main solid edge */}
      <BezierEdge
        {...props}
        style={{
          stroke: selected ? "#3b82f6" : "#ffffff",
          strokeWidth: selected ? 3 : 2.5,
        }}
      />
    </>
  );
}

export const FlowEdge = memo(FlowEdgeInner);
