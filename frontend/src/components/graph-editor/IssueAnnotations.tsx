/**
 * Renders draggable, resizable issue annotation boxes on the React Flow canvas
 * with hover popout for viewing issue details without leaving the graph.
 */

import { useRef, useState, useCallback } from "react";
import { useViewport } from "@xyflow/react";
import { useNavigate } from "react-router-dom";
import { CircleDot, GripVertical, ExternalLink } from "lucide-react";
import { issueStatusColors, issueStatusLabels } from "@/lib/utils";
import type { GraphIssueItem, GraphAnnotation } from "@/types/api";

const MIN_WIDTH = 120;
const MIN_HEIGHT = 60;

interface IssueAnnotationsProps {
  issues: GraphIssueItem[];
  onSaveAnnotation: (issueId: string, annotation: GraphAnnotation) => void;
  onDoubleClickIssue?: (issueId: string) => void;
}

type DragState = {
  issueId: string;
  mode: "move" | "resize";
  startMouseX: number;
  startMouseY: number;
  startX: number;
  startY: number;
  startW: number;
  startH: number;
};

export function IssueAnnotations({ issues, onSaveAnnotation, onDoubleClickIssue }: IssueAnnotationsProps) {
  const { x: viewX, y: viewY, zoom } = useViewport();
  const navigate = useNavigate();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [localOverrides, setLocalOverrides] = useState<Record<string, Partial<GraphAnnotation>>>({});
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, issue: GraphIssueItem, mode: "move" | "resize") => {
      e.stopPropagation();
      e.preventDefault();
      const ann = issue.graph_annotation;
      setDragState({
        issueId: issue.id,
        mode,
        startMouseX: e.clientX,
        startMouseY: e.clientY,
        startX: ann.x,
        startY: ann.y,
        startW: ann.width,
        startH: ann.height,
      });

      const handleMouseMove = (ev: MouseEvent) => {
        const dx = (ev.clientX - e.clientX) / zoom;
        const dy = (ev.clientY - e.clientY) / zoom;

        setLocalOverrides((prev) => {
          if (mode === "move") {
            return {
              ...prev,
              [issue.id]: {
                x: ann.x + dx,
                y: ann.y + dy,
              },
            };
          } else {
            return {
              ...prev,
              [issue.id]: {
                width: Math.max(MIN_WIDTH, ann.width + dx),
                height: Math.max(MIN_HEIGHT, ann.height + dy),
              },
            };
          }
        });
      };

      const handleMouseUp = (ev: MouseEvent) => {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("mouseup", handleMouseUp);

        const finalDx = (ev.clientX - e.clientX) / zoom;
        const finalDy = (ev.clientY - e.clientY) / zoom;

        const updated: GraphAnnotation = { ...ann };
        if (mode === "move") {
          updated.x = ann.x + finalDx;
          updated.y = ann.y + finalDy;
        } else {
          updated.width = Math.max(MIN_WIDTH, ann.width + finalDx);
          updated.height = Math.max(MIN_HEIGHT, ann.height + finalDy);
        }

        // Only save if there was actual movement
        if (Math.abs(ev.clientX - e.clientX) > 2 || Math.abs(ev.clientY - e.clientY) > 2) {
          onSaveAnnotation(issue.id, updated);
        }

        setLocalOverrides((prev) => {
          const next = { ...prev };
          delete next[issue.id];
          return next;
        });
        setDragState(null);
      };

      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    },
    [zoom, onSaveAnnotation]
  );

  const handleMouseEnter = useCallback((issueId: string) => {
    clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => setHoveredId(issueId), 300);
  }, []);

  const handleMouseLeave = useCallback(() => {
    clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => setHoveredId(null), 200);
  }, []);

  if (issues.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-[1] overflow-hidden">
      {issues.map((issue) => {
        const ann = issue.graph_annotation;
        const override = localOverrides[issue.id];
        const x = override?.x ?? ann.x;
        const y = override?.y ?? ann.y;
        const w = override?.width ?? ann.width;
        const h = override?.height ?? ann.height;

        const screenX = x * zoom + viewX;
        const screenY = y * zoom + viewY;
        const screenW = w * zoom;
        const screenH = h * zoom;

        const isDragging = dragState?.issueId === issue.id;
        const isHovered = hoveredId === issue.id && !dragState;

        return (
          <div
            key={issue.id}
            className="absolute pointer-events-none"
            style={{
              transform: `translate(${screenX}px, ${screenY}px)`,
              width: screenW,
              height: screenH,
            }}
          >
            {/* Annotation box — visual only, clicks pass through to nodes */}
            <div
              className={`w-full h-full border-2 rounded-md flex flex-col p-1.5 overflow-hidden transition-colors ${
                isDragging
                  ? "border-amber-400 bg-amber-500/20"
                  : "border-amber-500/60 bg-amber-500/10"
              }`}
            >
              {/* Drag handle header — only interactive part */}
              <div
                className="flex items-center gap-1 mb-0.5 cursor-grab active:cursor-grabbing pointer-events-auto"
                onMouseDown={(e) => handleMouseDown(e, issue, "move")}
                onMouseEnter={() => handleMouseEnter(issue.id)}
                onMouseLeave={handleMouseLeave}
                onDoubleClick={() => onDoubleClickIssue?.(issue.id)}
              >
                <GripVertical
                  className="w-3 h-3 text-amber-400/60 shrink-0"
                  style={{ minWidth: 12 }}
                />
                <CircleDot
                  className="w-3 h-3 text-amber-400 shrink-0"
                  style={{ minWidth: 12 }}
                />
                <span
                  className="text-[10px] font-medium text-amber-200 truncate"
                  style={{ fontSize: Math.max(8, 10 * zoom) }}
                >
                  {issue.title}
                </span>
              </div>
              {/* Status badge */}
              <div className="flex items-center gap-1">
                <span
                  className={`text-[8px] px-1 py-0 rounded ${
                    issueStatusColors[issue.status] ?? "bg-gray-500/15 text-gray-400"
                  }`}
                  style={{ fontSize: Math.max(7, 8 * zoom) }}
                >
                  {issueStatusLabels[issue.status] ?? issue.status}
                </span>
                {issue.assigned_to && (
                  <span
                    className="text-[8px] text-amber-300/60 truncate"
                    style={{ fontSize: Math.max(7, 8 * zoom) }}
                  >
                    {issue.assigned_to.display_name}
                  </span>
                )}
              </div>
            </div>

            {/* Resize handle (bottom-right corner) */}
            <div
              className="absolute bottom-0 right-0 w-3 h-3 cursor-se-resize pointer-events-auto"
              onMouseDown={(e) => handleMouseDown(e, issue, "resize")}
            >
              <svg
                viewBox="0 0 12 12"
                className="w-full h-full text-amber-400/50 hover:text-amber-400"
              >
                <path d="M11 1v10H1" fill="none" stroke="currentColor" strokeWidth="1.5" />
                <path d="M11 5v6H5" fill="none" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </div>

            {/* Hover popout */}
            {isHovered && (
              <div
                className="absolute left-0 top-full mt-1 w-64 z-50 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] shadow-xl p-3"
                style={{ pointerEvents: "auto" }}
                onMouseEnter={() => {
                  clearTimeout(hoverTimeoutRef.current);
                  setHoveredId(issue.id);
                }}
                onMouseLeave={handleMouseLeave}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h4 className="text-sm font-semibold text-[var(--color-text)] leading-tight">
                    {issue.title}
                  </h4>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${
                      issueStatusColors[issue.status] ?? "bg-gray-500/15 text-gray-400"
                    }`}
                  >
                    {issueStatusLabels[issue.status] ?? issue.status}
                  </span>
                </div>

                {issue.description && (
                  <p className="text-xs text-[var(--color-text-muted)] mb-2 line-clamp-4 whitespace-pre-wrap">
                    {issue.description}
                  </p>
                )}

                {issue.assigned_to && (
                  <p className="text-[10px] text-[var(--color-text-muted)] mb-2">
                    Assigned to: <span className="text-[var(--color-text)]">{issue.assigned_to.display_name}</span>
                  </p>
                )}

                <button
                  type="button"
                  className="flex items-center gap-1 text-xs text-[var(--color-primary)] hover:underline"
                  onClick={() => navigate(`/issues/${issue.id}`)}
                >
                  <ExternalLink className="w-3 h-3" />
                  Open issue
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
