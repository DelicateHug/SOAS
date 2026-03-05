/**
 * Zustand store for the graph editor state.
 */

import { create } from "zustand";
import type { Node, Edge, OnNodesChange, OnEdgesChange, Connection } from "@xyflow/react";
import { applyNodeChanges, applyEdgeChanges, addEdge } from "@xyflow/react";
import type {
  VP2GraphData,
  NodeCatalogEntry,
  VP2Port,
  ValidationError,
  CompilationWarning,
} from "../types/graph";
import {
  vp2ToReactFlow,
  reactFlowToVP2,
  isFlowConnection,
  fromBackendFormat,
  type CustomNodeData,
} from "../utils/graphConversion";
import { PORT_TYPE_COLORS } from "../utils/portColors";

interface UndoState {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
}

interface ClipboardState {
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
}

interface GraphEditorState {
  // React Flow state
  nodes: Node<CustomNodeData>[];
  edges: Edge[];
  selectedNodeId: string | null;

  // Clipboard
  clipboard: ClipboardState | null;

  // Graph metadata
  graphId: string;
  name: string;
  description: string;
  triggerTags: string[];

  // Status flags
  isDirty: boolean;
  isSaving: boolean;
  isCompiling: boolean;
  isTestRunning: boolean;
  testRunExecutionId: string | null;

  // Undo/Redo
  undoStack: UndoState[];
  redoStack: UndoState[];

  // Validation & compilation
  validationErrors: ValidationError[];
  compilationWarnings: CompilationWarning[];
  generatedCode: string | null;
  nodeMap: Record<string, { type: string; label: string; start_line: number; end_line: number }> | null;

  // Actions - React Flow
  setNodes: (nodes: Node<CustomNodeData>[]) => void;
  setEdges: (edges: Edge[]) => void;
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: (connection: Connection) => void;

  // Actions - Node manipulation
  addNode: (catalogEntry: NodeCatalogEntry, position: { x: number; y: number }) => void;
  deleteSelected: () => void;
  selectNode: (nodeId: string | null) => void;
  copySelected: () => void;
  pasteClipboard: () => void;
  updateNodeProperty: (nodeId: string, property: string, value: unknown) => void;
  updateNodeInlineValue: (nodeId: string, portName: string, value: unknown) => void;
  updateNodeDynamicPorts: (
    nodeId: string,
    inputDefs: Array<{ name: string; type: string; required: boolean; default_value: unknown; description: string }>
  ) => void;
  updateStartNodeOutputs: (
    inputDefs: Array<{ name: string; type: string; required: boolean; default_value: unknown; description: string }>
  ) => void;

  // Actions - Undo/Redo
  undo: () => void;
  redo: () => void;
  pushUndoState: () => void;

  // Actions - Metadata
  setName: (name: string) => void;
  setDescription: (description: string) => void;
  setTriggerTags: (tags: string[]) => void;
  setGraphId: (id: string) => void;

  // Actions - Status
  setIsDirty: (dirty: boolean) => void;
  setIsSaving: (saving: boolean) => void;
  setIsCompiling: (compiling: boolean) => void;
  setIsTestRunning: (running: boolean) => void;
  setTestRunExecutionId: (id: string | null) => void;

  // Actions - Validation & compilation
  setValidationErrors: (errors: ValidationError[]) => void;
  setCompilationWarnings: (warnings: CompilationWarning[]) => void;
  setGeneratedCode: (code: string | null) => void;
  setNodeMap: (map: Record<string, { type: string; label: string; start_line: number; end_line: number }> | null) => void;

  // Actions - Serialization
  toVP2GraphData: () => VP2GraphData;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  loadFromVP2GraphData: (data: VP2GraphData | Record<string, any>, catalog: NodeCatalogEntry[]) => void;

  // Collaboration internals
  _isRemoteUpdate: boolean;
  _broadcastFn: ((op: string, payload: unknown) => void) | null;
  _setIsRemoteUpdate: (val: boolean) => void;
  _setBroadcastFn: (fn: ((op: string, payload: unknown) => void) | null) => void;
}

function generateNodeId(): string {
  return `node_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

function generateEdgeId(): string {
  return `edge_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

export const useGraphEditorStore = create<GraphEditorState>((set, get) => ({
  // Initial state
  nodes: [],
  edges: [],
  selectedNodeId: null,
  clipboard: null,

  graphId: "",
  name: "Untitled Graph",
  description: "",
  triggerTags: [],

  isDirty: false,
  isSaving: false,
  isCompiling: false,
  isTestRunning: false,
  testRunExecutionId: null,

  undoStack: [],
  redoStack: [],

  validationErrors: [],
  compilationWarnings: [],
  generatedCode: null,
  nodeMap: null,

  // Collaboration internals
  _isRemoteUpdate: false,
  _broadcastFn: null,
  _setIsRemoteUpdate: (val) => set({ _isRemoteUpdate: val }),
  _setBroadcastFn: (fn) => set({ _broadcastFn: fn }),

  // React Flow actions
  setNodes: (nodes) => set({ nodes, isDirty: true }),
  setEdges: (edges) => set({ edges, isDirty: true }),

  onNodesChange: (changes) => {
    const hasMeaningfulChange = (changes as Array<{ type: string }>).some(
      (c) => c.type !== "select" && c.type !== "dimensions"
    );
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes) as Node<CustomNodeData>[],
      ...(hasMeaningfulChange ? { isDirty: true } : {}),
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      const broadcastable = (changes as Array<{ type: string; dragging?: boolean }>).filter(
        (c) => c.type !== "select" && c.type !== "dimensions"
          // Skip mid-drag position changes — final position is broadcast on drag stop
          && !(c.type === "position" && c.dragging)
      );
      if (broadcastable.length > 0) {
        _broadcastFn("nodes_change", { changes: broadcastable });
      }
    }
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      isDirty: true,
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("edges_change", { changes });
    }
  },

  onConnect: (connection) => {
    const state = get();

    // Determine if this is a FLOW or data connection for edge type
    const isFlow = isFlowConnection(
      connection.sourceHandle || "",
      state.nodes
    );

    // Find the source port type for coloring
    let portType = "ANY";
    const sourceNode = state.nodes.find((n) => n.id === connection.source);
    if (sourceNode) {
      const data = sourceNode.data as CustomNodeData;
      const port = data.outputs.find(
        (p: VP2Port) => p.name === connection.sourceHandle
      );
      if (port) portType = port.type;
    }

    state.pushUndoState();

    const newEdge: Edge = {
      id: generateEdgeId(),
      source: connection.source!,
      target: connection.target!,
      sourceHandle: connection.sourceHandle,
      targetHandle: connection.targetHandle,
      type: isFlow ? "flowEdge" : "dataEdge",
      data: {
        portType,
        color: PORT_TYPE_COLORS[portType as keyof typeof PORT_TYPE_COLORS] || PORT_TYPE_COLORS.ANY,
      },
    };

    set((s) => ({
      edges: addEdge(newEdge, s.edges),
      isDirty: true,
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("connect", { edge: newEdge });
    }
  },

  // Node manipulation
  addNode: (catalogEntry, position) => {
    const state = get();
    state.pushUndoState();

    const newNode: Node<CustomNodeData> = {
      id: generateNodeId(),
      type: "custom",
      position,
      data: {
        type: catalogEntry.type,
        label: catalogEntry.label,
        color: catalogEntry.color,
        inputs: catalogEntry.inputs.map((p) => ({ ...p })),
        outputs: catalogEntry.outputs.map((p) => ({ ...p })),
        properties: catalogEntry.properties.reduce(
          (acc, prop) => {
            acc[prop.name] = prop.default ?? null;
            return acc;
          },
          {} as Record<string, unknown>
        ),
        catalogEntry,
      },
    };

    set((s) => ({
      nodes: [...s.nodes, newNode],
      isDirty: true,
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("add_node", { node: newNode });
    }
  },

  deleteSelected: () => {
    const state = get();
    const selectedNodes = state.nodes.filter((n) => n.selected);
    const selectedEdges = state.edges.filter((e) => e.selected);
    if (selectedNodes.length === 0 && selectedEdges.length === 0) return;

    state.pushUndoState();

    const selectedNodeIds = new Set(selectedNodes.map((n) => n.id));
    const selectedEdgeIds = new Set(selectedEdges.map((e) => e.id));
    set((s) => ({
      nodes: s.nodes.filter((n) => !selectedNodeIds.has(n.id)),
      edges: s.edges.filter(
        (e) =>
          !selectedEdgeIds.has(e.id) &&
          !selectedNodeIds.has(e.source) &&
          !selectedNodeIds.has(e.target)
      ),
      selectedNodeId:
        s.selectedNodeId && selectedNodeIds.has(s.selectedNodeId)
          ? null
          : s.selectedNodeId,
      isDirty: true,
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      if (selectedNodeIds.size > 0) {
        _broadcastFn("delete_nodes", { nodeIds: [...selectedNodeIds] });
      }
      if (selectedEdgeIds.size > 0) {
        _broadcastFn("edges_change", {
          changes: [...selectedEdgeIds].map((id) => ({ type: "remove", id })),
        });
      }
    }
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  copySelected: () => {
    const state = get();
    const selectedNodes = state.nodes.filter((n) => n.selected);
    if (selectedNodes.length === 0) return;

    const selectedNodeIds = new Set(selectedNodes.map((n) => n.id));
    // Copy edges that connect two selected nodes
    const connectedEdges = state.edges.filter(
      (e) => selectedNodeIds.has(e.source) && selectedNodeIds.has(e.target)
    );

    set({
      clipboard: {
        nodes: JSON.parse(JSON.stringify(selectedNodes)),
        edges: JSON.parse(JSON.stringify(connectedEdges)),
      },
    });
  },

  pasteClipboard: () => {
    const state = get();
    if (!state.clipboard || state.clipboard.nodes.length === 0) return;

    state.pushUndoState();

    // Map old IDs to new IDs
    const idMap = new Map<string, string>();
    const offset = { x: 50, y: 50 };

    const newNodes: Node<CustomNodeData>[] = state.clipboard.nodes.map((node) => {
      const newId = generateNodeId();
      idMap.set(node.id, newId);
      return {
        ...node,
        id: newId,
        position: {
          x: node.position.x + offset.x,
          y: node.position.y + offset.y,
        },
        selected: true,
      };
    });

    const newEdges: Edge[] = state.clipboard.edges.map((edge) => ({
      ...edge,
      id: generateEdgeId(),
      source: idMap.get(edge.source) || edge.source,
      target: idMap.get(edge.target) || edge.target,
      selected: false,
    }));

    // Deselect existing nodes, add pasted nodes as selected
    set((s) => ({
      nodes: [
        ...s.nodes.map((n) => ({ ...n, selected: false })),
        ...newNodes,
      ],
      edges: [...s.edges, ...newEdges],
      isDirty: true,
      selectedNodeId: newNodes.length === 1 ? newNodes[0]!.id : null,
    }));

    // Update clipboard positions so next paste offsets further
    set({
      clipboard: {
        nodes: JSON.parse(JSON.stringify(newNodes)),
        edges: JSON.parse(JSON.stringify(newEdges)),
      },
    });

    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      for (const node of newNodes) {
        _broadcastFn("add_node", { node });
      }
      for (const edge of newEdges) {
        _broadcastFn("connect", { edge });
      }
    }
  },

  updateNodeProperty: (nodeId, property, value) => {
    set((state) => ({
      nodes: state.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        const data = node.data as CustomNodeData;
        // Also sync to matching input port inline_value so the compiler picks it up
        const hasMatchingPort = data.inputs.some((p) => p.name === property);
        // Update node label when automation_name changes on run_automation nodes
        const newLabel =
          property === "automation_name" && data.type === "run_automation"
            ? (value as string) || data.catalogEntry?.label || "Run Automation"
            : data.label;
        return {
          ...node,
          data: {
            ...data,
            label: newLabel,
            properties: { ...data.properties, [property]: value },
            inputs: hasMatchingPort
              ? data.inputs.map((port) =>
                  port.name === property
                    ? { ...port, inline_value: value as string | number | boolean | null }
                    : port
                )
              : data.inputs,
          },
        };
      }),
      isDirty: true,
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("update_node_property", { nodeId, property, value });
    }
  },

  updateNodeInlineValue: (nodeId, portName, value) => {
    set((state) => ({
      nodes: state.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        const data = node.data as CustomNodeData;
        // Also sync to matching node property so the UI stays in sync
        const hasMatchingProp = portName in data.properties;
        return {
          ...node,
          data: {
            ...data,
            properties: hasMatchingProp
              ? { ...data.properties, [portName]: value }
              : data.properties,
            inputs: data.inputs.map((port) =>
              port.name === portName ? { ...port, inline_value: value as string | number | boolean | null } : port
            ),
          },
        };
      }),
      isDirty: true,
    }));
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("update_node_inline_value", { nodeId, portName, value });
    }
  },

  updateNodeDynamicPorts: (nodeId, inputDefs) => {
    const state = get();
    state.pushUndoState();

    set((s) => {
      // Build new port names for edge cleanup
      const dynamicPortNames = new Set(inputDefs.map((d) => d.name));

      return {
        nodes: s.nodes.map((node) => {
          if (node.id !== nodeId) return node;
          const data = node.data as CustomNodeData;

          // Keep FLOW ports, remove all data input ports
          const flowInputs = data.inputs.filter((p) => p.type === "FLOW");

          // Build new data inputs from the automation's parameter definitions
          const dynamicInputs: VP2Port[] = inputDefs.map((def) => ({
            name: def.name,
            type: (def.type || "ANY") as VP2Port["type"],
            label: def.name,
            inline_value: def.default_value as VP2Port["inline_value"] ?? null,
            required: def.required,
          }));

          return {
            ...node,
            data: {
              ...data,
              inputs: [...flowInputs, ...dynamicInputs],
            },
          };
        }),
        // Clean up edges connected to removed ports on this node
        edges: s.edges.filter((edge) => {
          if (edge.target !== nodeId) return true;
          const targetPort = edge.targetHandle || "";
          // Keep edges to FLOW ports or to valid dynamic ports
          if (targetPort === "exec_in") return true;
          return dynamicPortNames.has(targetPort);
        }),
        isDirty: true,
      };
    });
  },

  updateStartNodeOutputs: (inputDefs) => {
    const state = get();
    state.pushUndoState();

    set((s) => {
      const dynamicPortNames = new Set(inputDefs.map((d) => d.name));
      const startNodeIds = new Set(
        s.nodes
          .filter((n) => (n.data as CustomNodeData).type === "start")
          .map((n) => n.id)
      );

      return {
        nodes: s.nodes.map((node) => {
          const data = node.data as CustomNodeData;
          if (data.type !== "start") return node;

          // Keep FLOW outputs (exec_out), remove all data outputs
          const flowOutputs = data.outputs.filter((p) => p.type === "FLOW");

          // Build new data outputs from the automation's input definitions
          const dynamicOutputs: VP2Port[] = inputDefs.map((def) => ({
            name: def.name,
            type: (def.type || "ANY") as VP2Port["type"],
            label: def.name,
          }));

          return {
            ...node,
            data: {
              ...data,
              outputs: [...flowOutputs, ...dynamicOutputs],
              properties: { ...data.properties, _input_defs: inputDefs },
            },
          };
        }),
        // Clean up edges from start nodes to removed output ports
        edges: s.edges.filter((edge) => {
          if (!startNodeIds.has(edge.source)) return true;
          const sourcePort = edge.sourceHandle || "";
          if (sourcePort === "exec_out") return true;
          return dynamicPortNames.has(sourcePort);
        }),
        isDirty: true,
      };
    });

    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("update_start_outputs", { inputDefs });
    }
  },

  // Undo/Redo
  pushUndoState: () => {
    const { nodes, edges, undoStack } = get();
    const snapshot: UndoState = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };
    // Limit undo stack to 50 entries
    const newStack = [...undoStack, snapshot].slice(-50);
    set({ undoStack: newStack, redoStack: [] });
  },

  undo: () => {
    const { undoStack, nodes, edges } = get();
    if (undoStack.length === 0) return;

    const previous = undoStack[undoStack.length - 1]!;
    const currentSnapshot: UndoState = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };

    set((state) => ({
      nodes: previous.nodes as Node<CustomNodeData>[],
      edges: previous.edges,
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [...state.redoStack, currentSnapshot],
      isDirty: true,
    }));
  },

  redo: () => {
    const { redoStack, nodes, edges } = get();
    if (redoStack.length === 0) return;

    const next = redoStack[redoStack.length - 1]!;
    const currentSnapshot: UndoState = {
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    };

    set((state) => ({
      nodes: next.nodes as Node<CustomNodeData>[],
      edges: next.edges,
      redoStack: state.redoStack.slice(0, -1),
      undoStack: [...state.undoStack, currentSnapshot],
      isDirty: true,
    }));
  },

  // Metadata
  setName: (name) => {
    set({ name, isDirty: true });
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("set_metadata", { field: "name", value: name });
    }
  },
  setDescription: (description) => {
    set({ description, isDirty: true });
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("set_metadata", { field: "description", value: description });
    }
  },
  setTriggerTags: (triggerTags) => {
    set({ triggerTags, isDirty: true });
    const { _isRemoteUpdate, _broadcastFn } = get();
    if (!_isRemoteUpdate && _broadcastFn) {
      _broadcastFn("set_metadata", { field: "triggerTags", value: triggerTags });
    }
  },
  setGraphId: (graphId) => set({ graphId }),

  // Status
  setIsDirty: (isDirty) => set({ isDirty }),
  setIsSaving: (isSaving) => set({ isSaving }),
  setIsCompiling: (isCompiling) => set({ isCompiling }),
  setIsTestRunning: (isTestRunning) => set({ isTestRunning }),
  setTestRunExecutionId: (testRunExecutionId) => set({ testRunExecutionId }),

  // Validation & compilation
  setValidationErrors: (validationErrors) => set({ validationErrors }),
  setCompilationWarnings: (compilationWarnings) => set({ compilationWarnings }),
  setGeneratedCode: (generatedCode) => set({ generatedCode }),
  setNodeMap: (nodeMap) => set({ nodeMap }),

  // Serialization
  toVP2GraphData: () => {
    const { nodes, edges, graphId, name, description, triggerTags } = get();
    return reactFlowToVP2(
      nodes,
      edges,
      { name, description, triggerTags },
      graphId
    );
  },

  loadFromVP2GraphData: (rawData, catalog) => {
    // Normalize from backend format (metadata wrapper, input_ports, etc.) to frontend format
    const data = fromBackendFormat(rawData as Record<string, unknown>);
    const { nodes, edges } = vp2ToReactFlow(data, catalog);
    set({
      nodes: nodes as Node<CustomNodeData>[],
      edges,
      graphId: data.id,
      name: data.name,
      description: data.description,
      triggerTags: data.trigger_tags || [],
      isDirty: false,
      undoStack: [],
      redoStack: [],
      validationErrors: [],
      compilationWarnings: [],
      generatedCode: null,
      nodeMap: null,
      selectedNodeId: null,
    });
  },
}));
