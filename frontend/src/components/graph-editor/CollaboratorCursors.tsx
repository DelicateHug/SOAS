/**
 * SVG cursor overlays for remote collaborators on the graph canvas.
 * Uses React Flow viewport to convert flow coordinates to screen position.
 */

import { useViewport } from "@xyflow/react";
import type { Collaborator } from "./hooks/useCollaboration";

interface CollaboratorCursorsProps {
  collaborators: Collaborator[];
  myUserId: string;
}

export function CollaboratorCursors({
  collaborators,
  myUserId,
}: CollaboratorCursorsProps) {
  const { x: viewX, y: viewY, zoom } = useViewport();

  const others = collaborators.filter(
    (c) => c.user_id !== myUserId && c.cursor
  );

  if (others.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-50 overflow-hidden">
      {others.map((c) => {
        const screenX = c.cursor!.x * zoom + viewX;
        const screenY = c.cursor!.y * zoom + viewY;

        return (
          <div
            key={c.user_id}
            className="absolute transition-transform duration-75"
            style={{ transform: `translate(${screenX}px, ${screenY}px)` }}
          >
            {/* Cursor arrow */}
            <svg
              width="16"
              height="20"
              viewBox="0 0 16 20"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M0 0L16 12L8 12L4 20L0 0Z" fill={c.color} />
            </svg>
            {/* Name label */}
            <span
              className="absolute left-4 top-4 text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap text-white font-medium shadow-sm"
              style={{ backgroundColor: c.color }}
            >
              {c.display_name}
            </span>
          </div>
        );
      })}
    </div>
  );
}
