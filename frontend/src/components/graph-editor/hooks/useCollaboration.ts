/**
 * Hook for real-time graph collaboration via WebSocket.
 * Manages presence, remote cursors, lock state, and operation broadcasting.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useGraphEditorStore } from "../stores/graphEditorStore";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";
import type { Node, Edge } from "@xyflow/react";
import type { CustomNodeData } from "../utils/graphConversion";

export interface Collaborator {
  user_id: string;
  username: string;
  display_name: string;
  color: string;
  can_edit: boolean;
  cursor?: { x: number; y: number };
}

export interface LockState {
  user_id: string;
  display_name?: string;
  locked_at: string;
}

interface CollabMessage {
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

export interface UseCollaborationReturn {
  collaborators: Collaborator[];
  lockState: LockState | null;
  isConnected: boolean;
  isLockedByMe: boolean;
  isLockedByOther: boolean;
  isReadOnly: boolean;
  requestLock: () => void;
  releaseLock: () => void;
  broadcastCursor: (x: number, y: number) => void;
  broadcastIssuesChanged: () => void;
}

export function useCollaboration(
  automationId: string | undefined
): UseCollaborationReturn {
  const user = useAuthStore((s) => s.user);
  const myUserId = user?.id ?? "";
  const queryClient = useQueryClient();

  const [collaborators, setCollaborators] = useState<Map<string, Collaborator>>(
    new Map()
  );
  const [lockState, setLockState] = useState<LockState | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastCursorBroadcast = useRef(0);
  const reconnectDelay = useRef(1000);

  // Derived state
  const isLockedByMe = lockState?.user_id === myUserId;
  const isLockedByOther = lockState !== null && lockState.user_id !== myUserId;
  const isReadOnly = isLockedByOther;

  // -----------------------------------------------------------------------
  // Apply remote graph operations to the local store
  // -----------------------------------------------------------------------
  const applyRemoteOp = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (op: string, payload: any) => {
      const store = useGraphEditorStore.getState();
      store._setIsRemoteUpdate(true);

      try {
        switch (op) {
          case "nodes_change":
            store.onNodesChange(payload.changes);
            break;
          case "edges_change":
            store.onEdgesChange(payload.changes);
            break;
          case "connect":
            store.setEdges([...store.edges, payload.edge as Edge]);
            break;
          case "add_node":
            store.setNodes([
              ...store.nodes,
              payload.node as Node<CustomNodeData>,
            ]);
            break;
          case "delete_nodes": {
            const idsToDelete = new Set<string>(payload.nodeIds);
            store.setNodes(
              store.nodes.filter((n) => !idsToDelete.has(n.id))
            );
            store.setEdges(
              store.edges.filter(
                (e) => !idsToDelete.has(e.source) && !idsToDelete.has(e.target)
              )
            );
            break;
          }
          case "update_node_property":
            store.updateNodeProperty(
              payload.nodeId,
              payload.property,
              payload.value
            );
            break;
          case "update_node_inline_value":
            store.updateNodeInlineValue(
              payload.nodeId,
              payload.portName,
              payload.value
            );
            break;
          case "set_metadata":
            if (payload.field === "name") store.setName(payload.value);
            if (payload.field === "description")
              store.setDescription(payload.value);
            if (payload.field === "triggerTags")
              store.setTriggerTags(payload.value);
            break;
        }
      } finally {
        store._setIsRemoteUpdate(false);
      }
    },
    []
  );

  // -----------------------------------------------------------------------
  // Handle incoming WebSocket messages
  // -----------------------------------------------------------------------
  const handleMessageRef = useRef<(msg: CollabMessage) => void>(() => {});
  const handleMessage = useCallback(
    (msg: CollabMessage) => {
      switch (msg.type) {
        case "session_state":
          {
            const map = new Map<string, Collaborator>();
            for (const c of msg.collaborators as Collaborator[]) {
              map.set(c.user_id, c);
            }
            setCollaborators(map);
            setLockState(msg.lock ?? null);
          }
          break;

        case "user_joined":
          setCollaborators((prev) => {
            const next = new Map(prev);
            next.set(msg.user_id, {
              user_id: msg.user_id,
              username: msg.username,
              display_name: msg.display_name,
              color: msg.color,
              can_edit: true,
            });
            return next;
          });
          break;

        case "user_left":
          setCollaborators((prev) => {
            const next = new Map(prev);
            next.delete(msg.user_id);
            return next;
          });
          break;

        case "cursor_move":
          setCollaborators((prev) => {
            const existing = prev.get(msg.user_id);
            if (!existing) return prev;
            const next = new Map(prev);
            next.set(msg.user_id, {
              ...existing,
              cursor: { x: msg.x, y: msg.y },
            });
            return next;
          });
          break;

        case "graph_op":
          applyRemoteOp(msg.op, msg.payload);
          break;

        case "lock_acquired":
          setLockState({
            user_id: msg.user_id,
            display_name: msg.display_name,
            locked_at: new Date().toISOString(),
          });
          break;

        case "lock_released":
          setLockState(null);
          break;

        case "lock_denied":
          // Silently ignore — UI already shows the lock state
          break;

        case "issues_changed":
          // Another collaborator created/moved/resized an issue annotation
          queryClient.invalidateQueries({
            queryKey: ["automation-graph-issues", automationId],
          });
          break;
      }
    },
    [applyRemoteOp, queryClient, automationId]
  );

  // Keep the ref in sync so the WebSocket effect always calls the latest handler
  handleMessageRef.current = handleMessage;

  // -----------------------------------------------------------------------
  // Broadcast function registered with the store
  // -----------------------------------------------------------------------
  const broadcastOp = useCallback((op: string, payload: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "graph_op", op, payload })
      );
    }
  }, []);

  // Register/unregister broadcast function on the store
  useEffect(() => {
    if (automationId) {
      useGraphEditorStore.getState()._setBroadcastFn(broadcastOp);
    }
    return () => {
      useGraphEditorStore.getState()._setBroadcastFn(null);
    };
  }, [automationId, broadcastOp]);

  // -----------------------------------------------------------------------
  // WebSocket connection with reconnection
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!automationId) return;

    const token = api.getAccessToken();
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/v1/ws/collaboration/${automationId}?token=${token}`;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectDelay.current = 1000;

        // Start heartbeat
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "heartbeat" }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string) as CollabMessage;
          handleMessageRef.current(msg);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        // Will trigger onclose
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (heartbeatRef.current) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
        }

        // Reconnect with exponential backoff
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelay.current = Math.min(
            reconnectDelay.current * 2,
            30000
          );
          connect();
        }, reconnectDelay.current);
      };
    }

    connect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setCollaborators(new Map());
      setLockState(null);
      setIsConnected(false);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- handleMessageRef is stable
  }, [automationId]);

  // -----------------------------------------------------------------------
  // Cursor broadcasting (throttled to 50ms)
  // -----------------------------------------------------------------------
  const broadcastCursor = useCallback((x: number, y: number) => {
    const now = Date.now();
    if (now - lastCursorBroadcast.current < 50) return;
    lastCursorBroadcast.current = now;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cursor_move", x, y }));
    }
  }, []);

  // -----------------------------------------------------------------------
  // Lock controls
  // -----------------------------------------------------------------------
  const requestLock = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "lock_request" }));
    }
  }, []);

  const releaseLock = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "unlock_request" }));
    }
  }, []);

  const broadcastIssuesChanged = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "issues_changed" }));
    }
  }, []);

  return {
    collaborators: Array.from(collaborators.values()),
    lockState,
    isConnected,
    isLockedByMe,
    isLockedByOther,
    isReadOnly,
    requestLock,
    releaseLock,
    broadcastCursor,
    broadcastIssuesChanged,
  };
}
