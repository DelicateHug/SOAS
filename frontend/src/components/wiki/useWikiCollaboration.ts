/**
 * Hook for real-time wiki page co-editing via Y.js + WebSocket.
 * Manages Y.js document, awareness (cursors), presence, and WebSocket lifecycle.
 */

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import * as Y from "yjs";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface WikiCollaborator {
  user_id: string;
  username: string;
  display_name: string;
  color: string;
  can_edit: boolean;
}

interface CollabMessage {
  type: string;
  [key: string]: unknown;
}

export interface UseWikiCollaborationReturn {
  /** The Y.js document for Tiptap collaboration */
  ydoc: Y.Doc;
  /** Connected collaborators (excluding self) */
  collaborators: WikiCollaborator[];
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Send a Y.js update to other clients */
  broadcastUpdate: (update: Uint8Array, fullState: Uint8Array) => void;
  /** Send a field update (title, tags, status, etc.) */
  broadcastFieldUpdate: (field: string, value: unknown) => void;
  /** Send rendered HTML for DB persistence */
  saveHtml: (html: string) => void;
  /** Save full Y.js state to backend */
  saveYjsState: (state: Uint8Array) => void;
  /** Callback for when a remote field update is received */
  onFieldUpdate: React.MutableRefObject<((field: string, value: unknown) => void) | null>;
}

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]!);
  }
  return btoa(binary);
}

function base64ToUint8(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWikiCollaboration(
  pageId: string | undefined
): UseWikiCollaborationReturn {
  const user = useAuthStore((s) => s.user);
  const myUserId = user?.id ?? "";

  const [collaborators, setCollaborators] = useState<Map<string, WikiCollaborator>>(
    new Map()
  );
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const deliberateClose = useRef(false);

  // Stable Y.js doc per page
  const ydocRef = useRef<Y.Doc | null>(null);
  if (!ydocRef.current) {
    ydocRef.current = new Y.Doc();
  }
  const ydoc = ydocRef.current;

  // Callback ref for field updates from remote
  const onFieldUpdateRef = useRef<((field: string, value: unknown) => void) | null>(null);

  // -----------------------------------------------------------------------
  // Handle incoming WebSocket messages
  // -----------------------------------------------------------------------
  const handleMessageRef = useRef<(msg: CollabMessage) => void>(() => {});
  const handleMessage = useCallback(
    (msg: CollabMessage) => {
      switch (msg.type) {
        case "session_state": {
          // Initial state: set collaborators and apply Y.js state
          const map = new Map<string, WikiCollaborator>();
          for (const c of (msg.collaborators as WikiCollaborator[]) ?? []) {
            if (c.user_id !== myUserId) {
              map.set(c.user_id, c);
            }
          }
          setCollaborators(map);

          // Apply persisted Y.js state if available
          if (msg.yjs_state) {
            try {
              const state = base64ToUint8(msg.yjs_state as string);
              Y.applyUpdate(ydoc, state);
            } catch {
              // Ignore invalid state
            }
          }
          break;
        }

        case "user_joined":
          setCollaborators((prev) => {
            if ((msg.user_id as string) === myUserId) return prev;
            const next = new Map(prev);
            next.set(msg.user_id as string, {
              user_id: msg.user_id as string,
              username: msg.username as string,
              display_name: msg.display_name as string,
              color: msg.color as string,
              can_edit: true,
            });
            return next;
          });
          break;

        case "user_left":
          setCollaborators((prev) => {
            const next = new Map(prev);
            next.delete(msg.user_id as string);
            return next;
          });
          break;

        case "yjs_update": {
          // Apply remote Y.js update
          try {
            const updateData = msg.update as string;
            if (updateData) {
              const update = base64ToUint8(updateData);
              Y.applyUpdate(ydoc, update);
            }
          } catch {
            // Ignore malformed updates
          }
          break;
        }

        case "field_update":
          // Remote metadata change (title, tags, status, etc.)
          if (onFieldUpdateRef.current) {
            onFieldUpdateRef.current(msg.field as string, msg.value);
          }
          break;
      }
    },
    [myUserId, ydoc]
  );

  handleMessageRef.current = handleMessage;

  // -----------------------------------------------------------------------
  // Broadcast functions
  // -----------------------------------------------------------------------
  const broadcastUpdate = useCallback(
    (update: Uint8Array, fullState: Uint8Array) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "yjs_update",
            update: uint8ToBase64(update),
            state: uint8ToBase64(fullState),
          })
        );
      }
    },
    []
  );

  const broadcastFieldUpdate = useCallback((field: string, value: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "field_update", field, value })
      );
    }
  }, []);

  const saveHtml = useCallback((html: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "save_html", html })
      );
    }
  }, []);

  const saveYjsState = useCallback((state: Uint8Array) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "save_yjs_state", state: uint8ToBase64(state) })
      );
    }
  }, []);

  // -----------------------------------------------------------------------
  // WebSocket connection with reconnection
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!pageId) return;

    const token = api.getAccessToken();
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/v1/ws/wiki/${pageId}?token=${token}`;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectDelay.current = 1000;
        reconnectAttempts.current = 0;

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

        if (deliberateClose.current) return;
        if (reconnectAttempts.current >= maxReconnectAttempts) {
          console.warn(
            `[WikiCollaboration] Gave up reconnecting after ${maxReconnectAttempts} attempts`
          );
          return;
        }

        reconnectAttempts.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelay.current = Math.min(
            reconnectDelay.current * 2,
            30000
          );
          connect();
        }, reconnectDelay.current);
      };
    }

    deliberateClose.current = false;
    reconnectAttempts.current = 0;
    connect();

    return () => {
      deliberateClose.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (wsRef.current) {
        if (
          wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING
        ) {
          // Save final Y.js state before disconnect
          try {
            const state = Y.encodeStateAsUpdate(ydoc);
            wsRef.current.send(
              JSON.stringify({ type: "save_yjs_state", state: uint8ToBase64(state) })
            );
          } catch {
            // Best effort
          }
          wsRef.current.close();
        }
        wsRef.current = null;
      }
      setCollaborators(new Map());
      setIsConnected(false);

      // Destroy and recreate ydoc for next mount
      ydoc.destroy();
      ydocRef.current = new Y.Doc();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageId]);

  const collaboratorList = useMemo(
    () => Array.from(collaborators.values()),
    [collaborators]
  );

  return {
    ydoc,
    collaborators: collaboratorList,
    isConnected,
    broadcastUpdate,
    broadcastFieldUpdate,
    saveHtml,
    saveYjsState,
    onFieldUpdate: onFieldUpdateRef,
  };
}
