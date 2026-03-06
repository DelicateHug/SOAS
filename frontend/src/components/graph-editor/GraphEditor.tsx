/**
 * Main graph editor component.
 * Composes React Flow canvas with all surrounding panels:
 * - Toolbar (top)
 * - NodePalette (left, collapsible)
 * - Canvas (center)
 * - PropertyPanel (right, collapsible)
 * - TestRunPanel / CodePreviewPanel (bottom, tabbed)
 */

import { memo, useCallback, useMemo, useRef, useState, useEffect, type DragEvent } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  type ReactFlowInstance,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { ChevronLeft, ChevronRight, Lock, X, Settings2, CircleDot } from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useGraphEditorStore } from "./stores/graphEditorStore";
import { useGraphSave } from "./hooks/useGraphSave";
import { useTestRun } from "./hooks/useTestRun";
import { useCompilePreview } from "./hooks/useCompilePreview";
import { useCollaboration } from "./hooks/useCollaboration";
import { useGraphIssues } from "./hooks/useGraphIssues";
import { CollaboratorCursors } from "./CollaboratorCursors";
import { IssueAnnotations } from "./IssueAnnotations";
import { CreateGraphIssueDialog } from "./CreateGraphIssueDialog";
import { useAuthStore } from "@/stores/authStore";
import { CustomNodeComponent } from "./nodes/CustomNodeComponent";
import { FlowEdge } from "./edges/FlowEdge";
import { DataEdge } from "./edges/DataEdge";
import { NodePalette } from "./NodePalette";
import { PropertyPanel } from "./PropertyPanel";
import { GraphIssuePanel } from "./GraphIssuePanel";
import { GraphEditorToolbar } from "./GraphEditorToolbar";
import { TestRunPanel } from "./TestRunPanel";
import { CodePreviewPanel } from "./CodePreviewPanel";
import { PermissionsPanel } from "./PermissionsPanel";
import { AutomationInputsDialog } from "./AutomationInputsDialog";
import TestContextDialog from "./TestContextDialog";
import type { TestContext } from "./hooks/useTestRun";
import type { NodeCatalogEntry } from "./types/graph";
import type { CustomNodeData } from "./utils/graphConversion";

/** Custom node type registry for React Flow */
const nodeTypes = {
  custom: CustomNodeComponent,
};

/** Custom edge type registry for React Flow */
const edgeTypes = {
  flowEdge: FlowEdge,
  dataEdge: DataEdge,
};

/**
 * Subscribes to nodes/edges from the Zustand store so drag-induced re-renders
 * are isolated here instead of cascading through the entire GraphEditor tree.
 */
const StoreConnectedFlow = memo(function StoreConnectedFlow(
  props: Omit<React.ComponentProps<typeof ReactFlow>, "nodes" | "edges">
) {
  const nodes = useGraphEditorStore((s) => s.nodes);
  const edges = useGraphEditorStore((s) => s.edges);
  return <ReactFlow nodes={nodes} edges={edges} {...props} />;
});

type BottomTab = "test-run" | "code-preview" | "errors";
type RightTab = "properties" | "issues";

interface Notification {
  type: "success" | "error" | "info";
  message: string;
}

interface GraphEditorProps {
  automationId?: string;
  automationVersion?: number;
  /** Called on first save for new automations — creates the automation and returns its ID */
  onCreateAutomation?: () => Promise<string>;
}

export function GraphEditor({ automationId, automationVersion = 1, onCreateAutomation }: GraphEditorProps) {
  const reactFlowRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const [reactFlowInstance, setReactFlowInstance] =
    useState<ReactFlowInstance | null>(null);
  const [bottomTab, setBottomTab] = useState<BottomTab>("test-run");
  const [bottomPanelHeight, setBottomPanelHeight] = useState(200);
  const [isBottomOpen, setIsBottomOpen] = useState(false);
  const [isLeftPanelOpen, setIsLeftPanelOpen] = useState(true);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [rightTab, setRightTab] = useState<RightTab>("properties");
  const [focusIssueId, setFocusIssueId] = useState<string | null>(null);
  const [notification, setNotification] = useState<Notification | null>(null);
  const [isPermissionsOpen, setIsPermissionsOpen] = useState(false);
  const [isInputsOpen, setIsInputsOpen] = useState(false);
  const [isTestContextOpen, setIsTestContextOpen] = useState(false);
  const lastTestContextRef = useRef<TestContext | null>(null);

  // Auto-dismiss notification after 4 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  // Store state — data selectors (trigger re-renders when data changes)
  // NOTE: nodes/edges are NOT subscribed here — they live in StoreConnectedFlow
  // to avoid re-rendering the entire editor tree on every drag frame.
  const validationErrors = useGraphEditorStore((s) => s.validationErrors);

  // Store actions — grouped with useShallow (stable refs, single subscription)
  const {
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    deleteSelected,
    selectNode,
    copySelected,
    pasteClipboard,
    setValidationErrors,
    updateStartNodeOutputs,
    pushUndoState,
    undo,
    redo,
  } = useGraphEditorStore(useShallow((s) => ({
    onNodesChange: s.onNodesChange,
    onEdgesChange: s.onEdgesChange,
    onConnect: s.onConnect,
    addNode: s.addNode,
    deleteSelected: s.deleteSelected,
    selectNode: s.selectNode,
    copySelected: s.copySelected,
    pasteClipboard: s.pasteClipboard,
    setValidationErrors: s.setValidationErrors,
    updateStartNodeOutputs: s.updateStartNodeOutputs,
    pushUndoState: s.pushUndoState,
    undo: s.undo,
    redo: s.redo,
  })));

  // Hooks
  const saveMutation = useGraphSave(automationId);
  const {
    startTestRun,
    isStarting: isTestRunStarting,
    outputLines,
    status: testRunStatus,
    pendingInput,
    respondToInput,
    clearOutput,
  } = useTestRun(automationId);
  const compileMutation = useCompilePreview();

  // Collaboration
  const currentUser = useAuthStore((s) => s.user);
  const {
    collaborators,
    lockState,
    isConnected: isCollabConnected,
    isLockedByMe,
    isLockedByOther,
    isReadOnly,
    requestLock,
    releaseLock,
    broadcastCursor,
    broadcastIssuesChanged,
  } = useCollaboration(automationId);

  // Graph issues
  const { issues: graphIssues, showIssues, setShowIssues, saveAnnotation } = useGraphIssues(automationId, broadcastIssuesChanged);
  const [isCreateGraphIssueOpen, setIsCreateGraphIssueOpen] = useState(false);
  const [graphIssuePosition, setGraphIssuePosition] = useState({ x: 0, y: 0 });

  const lockHolderName = isLockedByOther
    ? collaborators.find((c) => c.user_id === lockState?.user_id)?.display_name ??
      lockState?.display_name ??
      "another user"
    : undefined;

  // Handle node selection
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  const handlePaneClick = useCallback(
    (event: React.MouseEvent) => {
      selectNode(null);
      // If issues are visible and user double-clicks, open create dialog at that position
      if (showIssues && event.detail === 2 && reactFlowInstance && automationId) {
        const position = reactFlowInstance.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
        setGraphIssuePosition({ x: Math.round(position.x), y: Math.round(position.y) });
        setIsCreateGraphIssueOpen(true);
      }
    },
    [selectNode, showIssues, reactFlowInstance, automationId]
  );

  // Handle node drag/drop from palette
  const handleDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      const data = event.dataTransfer.getData("application/graph-editor-node");
      if (!data || !reactFlowInstance) return;

      try {
        const catalogEntry: NodeCatalogEntry = JSON.parse(data);

        // Convert screen coords to flow coords
        const position = reactFlowInstance.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });

        pushUndoState();
        addNode(catalogEntry, position);
      } catch {
        // Invalid drag data
      }
    },
    [reactFlowInstance, addNode, pushUndoState]
  );

  // Handle node drag stop to push undo
  const handleNodeDragStop = useCallback(() => {
    isDraggingRef.current = false;
  }, []);

  const handleNodeDragStart = useCallback(() => {
    isDraggingRef.current = true;
    pushUndoState();
  }, [pushUndoState]);

  // Broadcast cursor position to collaborators (skip during node drag to avoid overhead)
  const handleMouseMove = useCallback(
    (event: React.MouseEvent) => {
      if (!reactFlowInstance || isDraggingRef.current) return;
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      broadcastCursor(position.x, position.y);
    },
    [reactFlowInstance, broadcastCursor]
  );

  // Validate graph
  const handleValidate = useCallback(() => {
    const store = useGraphEditorStore.getState();
    const errors: Array<{ nodeId: string; message: string }> = [];

    for (const node of store.nodes) {
      const data = node.data as CustomNodeData;

      // Check if required inputs have connections or inline values
      for (const input of data.inputs) {
        if (input.type === "FLOW") continue;
        if (input.required === false) continue;

        const hasConnection = store.edges.some(
          (e) => e.target === node.id && e.targetHandle === input.name
        );
        const hasInlineValue =
          input.inline_value !== null &&
          input.inline_value !== undefined &&
          input.inline_value !== "";

        if (!hasConnection && !hasInlineValue) {
          errors.push({
            nodeId: node.id,
            message: `"${data.label}": Required input "${input.label || input.name}" has no connection and no value`,
          });
        }
      }
    }

    setValidationErrors(errors);

    if (errors.length === 0) {
      setNotification({ type: "success", message: "Validation passed - no errors found" });
    } else {
      setIsBottomOpen(true);
      setBottomTab("errors");
      setNotification({
        type: "error",
        message: `Validation found ${errors.length} error${errors.length !== 1 ? "s" : ""}`,
      });
    }
  }, [setValidationErrors]);

  // Compile preview
  const handleCompile = useCallback(() => {
    compileMutation.mutate(undefined, {
      onSuccess: () => {
        setNotification({ type: "success", message: "Code compiled successfully" });
      },
      onError: (error) => {
        const err = error as Error & { detail?: string };
        setNotification({
          type: "error",
          message: `Compile failed: ${err.detail || err.message || "Unknown error"}`,
        });
      },
    });
    setIsBottomOpen(true);
    setBottomTab("code-preview");
  }, [compileMutation]);

  // Test run - show context dialog
  const handleTestRun = useCallback(() => {
    if (!automationId) {
      setNotification({
        type: "error",
        message: "Cannot test run: automation not created yet. Try refreshing the page.",
      });
      return;
    }
    setIsTestContextOpen(true);
  }, [automationId]);

  // Execute test run with context
  const handleTestRunWithContext = useCallback(
    (context: TestContext) => {
      setIsTestContextOpen(false);
      lastTestContextRef.current = context;
      startTestRun(context);
      setIsBottomOpen(true);
      setBottomTab("test-run");
    },
    [startTestRun]
  );

  // Re-run test with the last used context
  const handleTestRunAgain = useCallback(() => {
    if (!automationId) return;
    if (!lastTestContextRef.current) return;
    startTestRun(lastTestContextRef.current);
    setIsBottomOpen(true);
    setBottomTab("test-run");
  }, [automationId, startTestRun]);

  const hasLastTestContext = lastTestContextRef.current !== null;

  // Save (runs validation first to warn about required inputs)
  const handleSave = useCallback(async () => {
    let currentId = automationId;

    // For new automations, create on the backend first
    if (!currentId && onCreateAutomation) {
      try {
        setNotification({ type: "info", message: "Creating automation..." });
        currentId = await onCreateAutomation();
      } catch (error: unknown) {
        const err = error as Error & { detail?: string };
        setNotification({
          type: "error",
          message: `Failed to create automation: ${err.detail || err.message || "Unknown error"}`,
        });
        return;
      }
    }

    if (!currentId) {
      setNotification({
        type: "error",
        message: "Cannot save: automation not created yet. Try refreshing the page.",
      });
      return;
    }

    // Run validation and surface errors before saving
    handleValidate();
    const errors = useGraphEditorStore.getState().validationErrors;
    if (errors.length > 0) {
      setNotification({
        type: "error",
        message: `${errors.length} validation error${errors.length !== 1 ? "s" : ""} found — check the error count for details. Save continues anyway.`,
      });
    }

    saveMutation.mutate(undefined, {
      onSuccess: () => {
        if (errors.length === 0) {
          setNotification({ type: "success", message: "Graph saved successfully" });
        }
      },
      onError: (error) => {
        const err = error as Error & { detail?: string };
        setNotification({
          type: "error",
          message: `Save failed: ${err.detail || err.message || "Unknown error"}`,
        });
      },
    });
  }, [automationId, onCreateAutomation, saveMutation, handleValidate]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+S: Save
      if (e.ctrlKey && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
      // Ctrl+Z: Undo
      if (e.ctrlKey && !e.shiftKey && e.key === "z") {
        e.preventDefault();
        undo();
      }
      // Ctrl+Shift+Z or Ctrl+Y: Redo
      if (
        (e.ctrlKey && e.shiftKey && e.key === "z") ||
        (e.ctrlKey && !e.shiftKey && e.key === "y")
      ) {
        e.preventDefault();
        redo();
      }
      // Delete/Backspace: Delete selected
      if (e.key === "Delete" || e.key === "Backspace") {
        const target = e.target as HTMLElement;
        if (
          target.tagName !== "INPUT" &&
          target.tagName !== "TEXTAREA" &&
          target.tagName !== "SELECT" &&
          !target.isContentEditable
        ) {
          deleteSelected();
        }
      }
      // Ctrl+C: Copy selected nodes
      if (e.ctrlKey && e.key === "c") {
        const target = e.target as HTMLElement;
        if (
          target.tagName !== "INPUT" &&
          target.tagName !== "TEXTAREA" &&
          target.tagName !== "SELECT" &&
          !target.isContentEditable
        ) {
          e.preventDefault();
          copySelected();
        }
      }
      // Ctrl+V: Paste nodes
      if (e.ctrlKey && e.key === "v") {
        const target = e.target as HTMLElement;
        if (
          target.tagName !== "INPUT" &&
          target.tagName !== "TEXTAREA" &&
          target.tagName !== "SELECT" &&
          !target.isContentEditable
        ) {
          e.preventDefault();
          pasteClipboard();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSave, undo, redo, deleteSelected, copySelected, pasteClipboard]);

  // Memoize inline props to prevent React Flow re-renders on every state change
  const defaultEdgeOptions = useMemo(() => ({ type: "dataEdge" as const }), []);
  const canvasStyle = useMemo(() => ({ background: "#0f0f1a" }), []);
  const miniMapNodeColor = useCallback((node: Node) => {
    const data = node.data as CustomNodeData;
    return data.color || "#6b7280";
  }, []);

  return (
    <ReactFlowProvider>
    <div className="flex flex-col h-full bg-[#0f0f1a]">
      {/* Toolbar */}
      <GraphEditorToolbar
        onSave={handleSave}
        onValidate={handleValidate}
        onCompile={handleCompile}
        onTestRun={handleTestRun}
        onTestRunAgain={handleTestRunAgain}
        hasLastTestContext={hasLastTestContext}
        onPermissions={() => {
          if (!automationId) {
            setNotification({ type: "error", message: "Cannot manage permissions: automation not created yet." });
            return;
          }
          setIsPermissionsOpen(true);
        }}
        onInputs={() => {
          if (!automationId) {
            setNotification({ type: "error", message: "Cannot define inputs: automation not created yet." });
            return;
          }
          setIsInputsOpen(true);
        }}
        onShowErrors={() => {
          setIsBottomOpen(true);
          setBottomTab("errors");
        }}
        isTestRunStarting={isTestRunStarting}
        isLeftPanelOpen={isLeftPanelOpen}
        isRightPanelOpen={isRightPanelOpen}
        onToggleLeftPanel={() => setIsLeftPanelOpen((v) => !v)}
        onToggleRightPanel={() => setIsRightPanelOpen((v) => !v)}
        collaborators={collaborators}
        myUserId={currentUser?.id ?? ""}
        isCollabConnected={isCollabConnected}
        isLockedByMe={isLockedByMe}
        isLockedByOther={isLockedByOther}
        lockHolderName={lockHolderName}
        onLockToggle={isLockedByMe ? releaseLock : requestLock}
        isReadOnly={isReadOnly}
        showIssues={showIssues}
        onToggleIssues={() => setShowIssues((v) => !v)}
        issueCount={graphIssues.length}
      />

      {/* Notification toast */}
      {notification && (
        <div
          className={`flex items-center gap-2 px-3 py-1.5 text-xs border-b ${
            notification.type === "error"
              ? "bg-red-500/10 text-red-400 border-red-500/20"
              : notification.type === "success"
                ? "bg-green-500/10 text-green-400 border-green-500/20"
                : "bg-blue-500/10 text-blue-400 border-blue-500/20"
          }`}
        >
          <span className="flex-1">{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            className="p-0.5 hover:opacity-70"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Locked by other user banner */}
      {isLockedByOther && (
        <div className="flex items-center gap-2 px-3 py-1 text-xs bg-amber-500/10 text-amber-400 border-b border-amber-500/20">
          <Lock className="w-3 h-3" />
          <span>This graph is locked by {lockHolderName}. You are viewing in read-only mode.</span>
        </div>
      )}

      {/* Main area: palette + canvas + properties */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Node Palette */}
        {isLeftPanelOpen ? (
          <NodePalette onCollapse={() => setIsLeftPanelOpen(false)} />
        ) : (
          <button
            onClick={() => setIsLeftPanelOpen(true)}
            className="w-8 border-r border-[hsl(var(--border))] bg-[hsl(var(--background))] flex items-center justify-center hover:bg-[hsl(var(--accent))] transition-colors"
            title="Show node palette"
          >
            <ChevronRight className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
          </button>
        )}

        {/* Center: Canvas + Bottom panel */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* React Flow canvas */}
          <div
            ref={reactFlowRef}
            className={`relative ${isBottomOpen ? "" : "flex-1"}`}
            style={isBottomOpen ? { flex: `1 1 0`, minHeight: 0 } : undefined}
            onMouseMove={handleMouseMove}
          >
            <StoreConnectedFlow
              onNodesChange={isReadOnly ? undefined : onNodesChange}
              onEdgesChange={isReadOnly ? undefined : onEdgesChange}
              onConnect={isReadOnly ? undefined : onConnect}
              onNodeClick={handleNodeClick}
              onPaneClick={handlePaneClick}
              onNodeDragStart={isReadOnly ? undefined : handleNodeDragStart}
              onNodeDragStop={isReadOnly ? undefined : handleNodeDragStop}
              onDragOver={isReadOnly ? undefined : handleDragOver}
              onDrop={isReadOnly ? undefined : handleDrop}
              onInit={setReactFlowInstance}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              nodesDraggable={!isReadOnly}
              nodesConnectable={!isReadOnly}
              elementsSelectable={!isReadOnly}
              fitView
              deleteKeyCode={null}
              defaultEdgeOptions={defaultEdgeOptions}
              style={canvasStyle}
            >
              <Background color="#1e1e2e" gap={20} size={1} />
              <Controls className="!bg-[#1a1a2e] !border-[#2a2a3e] !shadow-lg [&>button]:!bg-[#1a1a2e] [&>button]:!border-[#2a2a3e] [&>button]:!text-gray-300 [&>button:hover]:!bg-[#2a2a3e]" />
              <MiniMap
                className="!bg-[#1a1a2e] !border-[#2a2a3e]"
                nodeColor={miniMapNodeColor}
                maskColor="rgba(0,0,0,0.6)"
              />
              {/* Collaborator cursor overlay - must be inside ReactFlow for useViewport() */}
              <CollaboratorCursors
                collaborators={collaborators}
                myUserId={currentUser?.id ?? ""}
              />
            </StoreConnectedFlow>
              {/* Issue annotation overlay — rendered outside ReactFlow so the pane doesn't swallow clicks */}
              {showIssues && <IssueAnnotations issues={graphIssues} onSaveAnnotation={saveAnnotation} onDoubleClickIssue={(id) => { setRightTab("issues"); setIsRightPanelOpen(true); setFocusIssueId(id); }} />}
          </div>

          {/* Bottom panel (collapsible) */}
          {isBottomOpen && (
            <div
              className="flex-shrink-0 border-t border-[#2a2a3e] bg-[#0f0f1a]"
              style={{ height: bottomPanelHeight }}
            >
              {/* Tabs */}
              <div className="flex items-center border-b border-[#2a2a3e] bg-[#0f0f1a]">
                <button
                  onClick={() => setBottomTab("test-run")}
                  className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
                    bottomTab === "test-run"
                      ? "border-blue-500 text-gray-200"
                      : "border-transparent text-gray-500 hover:text-gray-300"
                  }`}
                >
                  Test Run
                </button>
                <button
                  onClick={() => setBottomTab("code-preview")}
                  className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors ${
                    bottomTab === "code-preview"
                      ? "border-blue-500 text-gray-200"
                      : "border-transparent text-gray-500 hover:text-gray-300"
                  }`}
                >
                  Code Preview
                </button>
                <button
                  onClick={() => setBottomTab("errors")}
                  className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                    bottomTab === "errors"
                      ? "border-red-500 text-gray-200"
                      : "border-transparent text-gray-500 hover:text-gray-300"
                  }`}
                >
                  Errors
                  {validationErrors.length > 0 && (
                    <span className="bg-red-500 text-white text-[10px] rounded-full px-1.5 min-w-[18px] text-center">
                      {validationErrors.length}
                    </span>
                  )}
                </button>
                <div className="flex-1" />
                <button
                  onClick={() => {
                    setBottomPanelHeight((h) =>
                      h === 200 ? 350 : 200
                    );
                  }}
                  className="px-2 py-1 text-[10px] text-gray-500 hover:text-gray-300"
                  title="Resize panel"
                >
                  {bottomPanelHeight === 350 ? "Shrink" : "Expand"}
                </button>
                <button
                  onClick={() => setIsBottomOpen(false)}
                  className="px-2 py-1 text-[10px] text-gray-500 hover:text-gray-300"
                  title="Close panel"
                >
                  Close
                </button>
              </div>

              {/* Tab content */}
              <div className="h-[calc(100%-32px)]">
                {bottomTab === "test-run" ? (
                  <TestRunPanel
                    outputLines={outputLines}
                    status={testRunStatus}
                    onClear={clearOutput}
                    pendingInput={pendingInput}
                    onSubmitInput={(value) => {
                      if (pendingInput) {
                        respondToInput(pendingInput.requestId, value, false);
                      }
                    }}
                    onCancelInput={() => {
                      if (pendingInput) {
                        respondToInput(pendingInput.requestId, "", true);
                      }
                    }}
                  />
                ) : bottomTab === "errors" ? (
                  <div className="flex flex-col h-full">
                    <div className="flex items-center justify-between px-3 py-1.5 border-b border-[hsl(var(--border))] bg-[hsl(var(--background))]">
                      <span className="text-xs font-semibold">
                        Validation Errors ({validationErrors.length})
                      </span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2">
                      {validationErrors.length === 0 ? (
                        <div className="text-gray-500 text-center py-4 text-xs">
                          No validation errors. Click "Validate" to check your graph.
                        </div>
                      ) : (
                        <div className="flex flex-col gap-1">
                          {validationErrors.map((err, i) => (
                            <button
                              key={i}
                              onClick={() => selectNode(err.nodeId)}
                              className="flex items-start gap-2 text-left w-full px-2 py-1.5 rounded hover:bg-red-500/10 transition-colors"
                            >
                              <span className="text-red-500 text-xs font-mono mt-0.5">{i + 1}.</span>
                              <span className="text-xs text-red-400">{err.message}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <CodePreviewPanel />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Property / Issues Panel */}
        {isRightPanelOpen ? (
          <div className="w-56 border-l border-[hsl(var(--border))] bg-[hsl(var(--background))] flex flex-col h-full overflow-hidden">
            {/* Tab bar */}
            <div className="flex border-b border-[hsl(var(--border))] shrink-0">
              <button
                onClick={() => setRightTab("properties")}
                className={`flex-1 flex items-center justify-center gap-1 px-1 py-1.5 text-[10px] font-medium border-b-2 transition-colors ${
                  rightTab === "properties"
                    ? "border-blue-500 text-[hsl(var(--foreground))]"
                    : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                }`}
              >
                <Settings2 className="w-3 h-3" />
                Properties
              </button>
              <button
                onClick={() => setRightTab("issues")}
                className={`flex-1 flex items-center justify-center gap-1 px-1 py-1.5 text-[10px] font-medium border-b-2 transition-colors ${
                  rightTab === "issues"
                    ? "border-amber-500 text-[hsl(var(--foreground))]"
                    : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                }`}
              >
                <CircleDot className="w-3 h-3" />
                Issues
                {graphIssues.length > 0 && (
                  <span className="text-[9px] bg-amber-500/20 text-amber-400 px-1 rounded-full">
                    {graphIssues.length}
                  </span>
                )}
              </button>
            </div>
            {/* Tab content */}
            <div className="flex-1 overflow-hidden">
              {rightTab === "properties" ? (
                <PropertyPanel isReadOnly={isReadOnly} />
              ) : automationId ? (
                <GraphIssuePanel
                  automationId={automationId}
                  issues={graphIssues}
                  onIssuesChanged={broadcastIssuesChanged}
                  focusIssueId={focusIssueId}
                  onFocusConsumed={() => setFocusIssueId(null)}
                />
              ) : null}
            </div>
          </div>
        ) : (
          <button
            onClick={() => setIsRightPanelOpen(true)}
            className="w-8 border-l border-[hsl(var(--border))] bg-[hsl(var(--background))] flex items-center justify-center hover:bg-[hsl(var(--accent))] transition-colors"
            title="Show properties"
          >
            <ChevronLeft className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
          </button>
        )}
      </div>

      {/* Permissions modal */}
      {isPermissionsOpen && automationId && (
        <PermissionsPanel
          automationId={automationId}
          onClose={() => setIsPermissionsOpen(false)}
        />
      )}

      {/* Automation Inputs modal */}
      {isInputsOpen && automationId && (
        <AutomationInputsDialog
          automationId={automationId}
          onClose={() => setIsInputsOpen(false)}
          onSave={(inputs) => updateStartNodeOutputs(inputs)}
        />
      )}

      {isTestContextOpen && (
        <TestContextDialog
          onRun={handleTestRunWithContext}
          onCancel={() => setIsTestContextOpen(false)}
          isRunning={isTestRunStarting}
        />
      )}

      {/* Create graph issue dialog */}
      {automationId && (
        <CreateGraphIssueDialog
          isOpen={isCreateGraphIssueOpen}
          onClose={() => setIsCreateGraphIssueOpen(false)}
          automationId={automationId}
          automationVersion={automationVersion}
          defaultX={graphIssuePosition.x}
          defaultY={graphIssuePosition.y}
          onCreated={broadcastIssuesChanged}
        />
      )}
    </div>
    </ReactFlowProvider>
  );
}
