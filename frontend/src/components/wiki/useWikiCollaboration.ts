/**
 * Hook for real-time wiki page co-editing via Y.js + WebSocket.
 * Manages Y.js document, awareness (cursors), presence, and WebSocket lifecycle.
 */

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import * as Y from "yjs";
import * as awarenessProtocol from "y-protocols/awareness";
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

/** Minimal provider interface that CollaborationCursor expects */
export interface AwarenessProvider {
  awareness: awarenessProtocol.Awareness;
}

export interface UseWikiCollaborationReturn {
  /** The Y.js document for Tiptap collaboration */
  ydoc: Y.Doc;
  /** Awareness provider for CollaborationCursor */
  provider: AwarenessProvider;
  /** Connected collaborators (excluding self) */
  collaborators: WikiCollaborator[];
  /** Whether the WebSocket is connected */
  isConnected: boolean;
  /** Whether the initial session state has been received and applied */
  sessionReady: boolean;
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
  const [sessionReady, setSessionReady] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const deliberateClose = useRef(false);

  // Stable Y.js doc per page – recreated only when pageId actually changes
  // (NOT in effect cleanup, which would break React StrictMode double-mount).
  const ydocRef = useRef<Y.Doc | null>(null);
  const awarenessRef = useRef<awarenessProtocol.Awareness | null>(null);
  const providerRef = useRef<AwarenessProvider | null>(null);
  const prevPageIdRef = useRef<string | undefined>();
  if (pageId !== prevPageIdRef.current) {
    if (ydocRef.current) ydocRef.current.destroy();
    ydocRef.current = new Y.Doc();
    awarenessRef.current = new awarenessProtocol.Awareness(ydocRef.current);
    providerRef.current = { awareness: awarenessRef.current };
    prevPageIdRef.current = pageId;
  }
  const ydoc = ydocRef.current!;
  const provider = providerRef.current!;

  // Callback ref for field updates from remote
  const onFieldUpdateRef = useRef<((field: string, value: unknown) => void) | null>(null);

  // -----------------------------------------------------------------------
  // Handle incoming WebSocket messages
  // -----------------------------------------------------------------------
  const handleMessageRef = useRef<(msg: CollabMessage) => void>(() => {});
  const handleMessage = useCallback(
    (msg: CollabMessage) => {
      // Always read ydocRef.current so we never operate on a destroyed doc
      // (prevents stale closure issues with React StrictMode double-mount).
      const doc = ydocRef.current;
      if (!doc) return;

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
              Y.applyUpdate(doc, state, "remote");
            } catch {
              // Ignore invalid state
            }
          }
          setSessionReady(true);
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
          // Apply remote Y.js update (origin="remote" prevents re-broadcast)
          try {
            const updateData = msg.update as string;
            if (updateData) {
              const update = base64ToUint8(updateData);
              Y.applyUpdate(doc, update, "remote");
            }
          } catch (err) {
            console.error("[WikiCollab] yjs_update error", err);
          }
          break;
        }

        case "awareness_update": {
          // Apply remote awareness (cursor positions, user info)
          try {
            const data = msg.data as string;
            if (data && awarenessRef.current) {
              awarenessProtocol.applyAwarenessUpdate(
                awarenessRef.current,
                base64ToUint8(data),
                "remote"
              );
            }
          } catch {
            // Ignore invalid awareness
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
    [myUserId]
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
  // Awareness: broadcast local cursor/selection changes to other clients
  // -----------------------------------------------------------------------
  useEffect(() => {
    const awareness = awarenessRef.current;
    if (!awareness) return;

    const handler = (
      { added, updated, removed }: { added: number[]; updated: number[]; removed: number[] },
      origin: unknown
    ) => {
      if (origin === "remote") return;
      const changed = added.concat(updated).concat(removed);
      const update = awarenessProtocol.encodeAwarenessUpdate(awareness, changed);
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: "awareness_update", data: uint8ToBase64(update) })
        );
      }
    };
    awareness.on("update", handler);
    return () => {
      awareness.off("update", handler);
    };
  }, [pageId]);

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
            const doc = ydocRef.current;
            if (doc) {
              const state = Y.encodeStateAsUpdate(doc);
              wsRef.current.send(
                JSON.stringify({ type: "save_yjs_state", state: uint8ToBase64(state) })
              );
            }
          } catch {
            // Best effort
          }
          wsRef.current.close();
        }
        wsRef.current = null;
      }
      setCollaborators(new Map());
      setIsConnected(false);
      setSessionReady(false);
      // NOTE: ydoc is NOT destroyed here — its lifecycle is managed during
      // render (via prevPageIdRef) so StrictMode double-mounts reuse the
      // same doc and the Tiptap editor stays in sync.
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageId]);

  const collaboratorList = useMemo(
    () => Array.from(collaborators.values()),
    [collaborators]
  );

  return {
    ydoc,
    provider,
    collaborators: collaboratorList,
    isConnected,
    sessionReady,
    broadcastUpdate,
    broadcastFieldUpdate,
    saveHtml,
    saveYjsState,
    onFieldUpdate: onFieldUpdateRef,
  };
}
