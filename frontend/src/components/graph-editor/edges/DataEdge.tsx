/**
 * Custom thin bezier edge for data connections.
 * Colored by the source port type.
 */

import { memo } from "react";
import { BezierEdge, type EdgeProps } from "@xyflow/react";

function DataEdgeInner(props: EdgeProps) {
  const edgeData = props.data as { color?: string } | undefined;
  const color = edgeData?.color || "#94a3b8";
  const selected = props.selected;

  return (
    <BezierEdge
      {...props}
      style={{
        stroke: selected ? "#3b82f6" : color,
        strokeWidth: selected ? 3 : 2,
      }}
    />
  );
}

export const DataEdge = memo(DataEdgeInner);
