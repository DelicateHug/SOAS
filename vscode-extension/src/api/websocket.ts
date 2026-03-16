/**
 * WebSocket manager for the extension host.
 * Manages WS connections to the SOAS backend and bridges messages to webviews.
 */

import WebSocket from "ws";
import { getServerUrl } from "../utils/config";
import { log, logError } from "../utils/notifications";

export interface WebSocketBridgeTarget {
  postMessage(message: unknown): Thenable<boolean>;
}

export class ManagedWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private disposed = false;
  private url: string;
  private bridge: WebSocketBridgeTarget | null = null;
  private wsId: string;

  constructor(url: string, wsId: string) {
    this.url = url;
    this.wsId = wsId;
  }

  setBridge(bridge: WebSocketBridgeTarget): void {
    this.bridge = bridge;
  }

  connect(token: string): void {
    if (this.disposed) return;

    // Convert http(s) to ws(s)
    const baseUrl = getServerUrl().replace(/^http/, "ws");
    const fullUrl = `${baseUrl}${this.url}?token=${token}`;

    log(`WebSocket connecting: ${this.url}`);

    this.ws = new WebSocket(fullUrl);

    this.ws.on("open", () => {
      log(`WebSocket connected: ${this.url}`);
      this.reconnectAttempts = 0;
      this.bridge?.postMessage({
        type: "ws-connected",
        wsId: this.wsId,
      });
    });

    this.ws.on("message", (data) => {
      const message = data.toString();
      this.bridge?.postMessage({
        type: "ws-message",
        wsId: this.wsId,
        data: message,
      });
    });

    this.ws.on("close", (code, reason) => {
      log(`WebSocket closed: ${this.url} (${code} ${reason.toString()})`);
      this.bridge?.postMessage({
        type: "ws-disconnected",
        wsId: this.wsId,
        code,
        reason: reason.toString(),
      });
      this.scheduleReconnect(token);
    });

    this.ws.on("error", (error) => {
      logError(`WebSocket error: ${this.url}`, error);
      this.bridge?.postMessage({
        type: "ws-error",
        wsId: this.wsId,
        error: error.message,
      });
    });
  }

  send(data: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  private scheduleReconnect(token: string): void {
    if (this.disposed || this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    log(`WebSocket reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect(token);
    }, delay);
  }

  close(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  dispose(): void {
    this.disposed = true;
    this.close();
  }
}

/**
 * Manages all WebSocket connections for a webview panel.
 * Handles ws-open, ws-send, ws-close messages from the webview and routes responses back.
 */
export class WebSocketManager {
  private connections = new Map<string, ManagedWebSocket>();
  private bridge: WebSocketBridgeTarget | null = null;
  private tokenGetter: () => Promise<string | undefined>;

  constructor(tokenGetter: () => Promise<string | undefined>) {
    this.tokenGetter = tokenGetter;
  }

  setBridge(bridge: WebSocketBridgeTarget): void {
    this.bridge = bridge;
  }

  async handleMessage(message: { type: string; wsId?: string; url?: string; data?: string }): Promise<void> {
    switch (message.type) {
      case "ws-open": {
        if (!message.url || !message.wsId) return;
        const token = await this.tokenGetter();
        if (!token) {
          logError("Cannot open WebSocket: no auth token");
          return;
        }
        const ws = new ManagedWebSocket(message.url, message.wsId);
        if (this.bridge) ws.setBridge(this.bridge);
        this.connections.set(message.wsId, ws);
        ws.connect(token);
        break;
      }
      case "ws-send": {
        if (!message.wsId || !message.data) return;
        const ws = this.connections.get(message.wsId);
        ws?.send(message.data);
        break;
      }
      case "ws-close": {
        if (!message.wsId) return;
        const ws = this.connections.get(message.wsId);
        ws?.close();
        this.connections.delete(message.wsId);
        break;
      }
    }
  }

  dispose(): void {
    for (const ws of this.connections.values()) {
      ws.dispose();
    }
    this.connections.clear();
  }
}
