/**
 * WebSocket bridge for webview.
 * Replaces the native browser WebSocket with a postMessage-based implementation
 * that routes through the extension host.
 *
 * This is assigned to globalThis.WebSocket before React mounts so that existing
 * hooks (useCollaboration, useTestRun) work without modification.
 */

import { getVsCodeApi } from "../vscode";

let wsIdCounter = 0;

export class WebSocketBridge {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;

  readyState: number = WebSocketBridge.CONNECTING;
  binaryType: string = "blob";
  bufferedAmount: number = 0;
  extensions: string = "";
  protocol: string = "";
  url: string;

  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  private wsId: string;
  private listeners: Map<string, Set<EventListener>> = new Map();

  constructor(url: string, _protocols?: string | string[]) {
    this.url = url;
    this.wsId = `ws_${++wsIdCounter}`;

    // Extract the path from the full URL (the extension host will construct the actual URL)
    const urlObj = new URL(url, "ws://placeholder");
    const path = urlObj.pathname + urlObj.search;

    // Request the extension host to open the WebSocket
    getVsCodeApi().postMessage({
      type: "ws-open",
      wsId: this.wsId,
      url: path,
    });

    // Listen for messages from extension host
    this.messageHandler = this.messageHandler.bind(this);
    window.addEventListener("message", this.messageHandler);
  }

  private messageHandler(event: MessageEvent): void {
    const msg = event.data;
    if (msg.wsId !== this.wsId) return;

    switch (msg.type) {
      case "ws-connected":
        this.readyState = WebSocketBridge.OPEN;
        this.dispatchEvent("open", new Event("open"));
        break;

      case "ws-message":
        this.dispatchEvent(
          "message",
          new MessageEvent("message", { data: msg.data })
        );
        break;

      case "ws-disconnected":
        this.readyState = WebSocketBridge.CLOSED;
        this.dispatchEvent(
          "close",
          new CloseEvent("close", { code: msg.code, reason: msg.reason })
        );
        this.cleanup();
        break;

      case "ws-error":
        this.dispatchEvent("error", new Event("error"));
        break;
    }
  }

  send(data: string | ArrayBuffer): void {
    if (this.readyState !== WebSocketBridge.OPEN) {
      throw new Error("WebSocket is not open");
    }
    getVsCodeApi().postMessage({
      type: "ws-send",
      wsId: this.wsId,
      data: typeof data === "string" ? data : String(data),
    });
  }

  close(code?: number, reason?: string): void {
    if (this.readyState === WebSocketBridge.CLOSED) return;
    this.readyState = WebSocketBridge.CLOSING;
    getVsCodeApi().postMessage({
      type: "ws-close",
      wsId: this.wsId,
    });
    this.readyState = WebSocketBridge.CLOSED;
    this.dispatchEvent(
      "close",
      new CloseEvent("close", { code: code ?? 1000, reason: reason ?? "" })
    );
    this.cleanup();
  }

  addEventListener(type: string, listener: EventListener): void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(listener);
  }

  removeEventListener(type: string, listener: EventListener): void {
    this.listeners.get(type)?.delete(listener);
  }

  private dispatchEvent(type: string, event: Event): void {
    // Call the on* handler
    const handler = (this as Record<string, unknown>)[`on${type}`];
    if (typeof handler === "function") {
      (handler as EventListener)(event);
    }

    // Call registered listeners
    const listeners = this.listeners.get(type);
    if (listeners) {
      for (const listener of listeners) {
        listener(event);
      }
    }
  }

  private cleanup(): void {
    window.removeEventListener("message", this.messageHandler);
  }
}

/**
 * Install the WebSocket bridge globally.
 * Call this before React mounts so existing hooks use the bridge.
 */
export function installWebSocketBridge(): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).WebSocket = WebSocketBridge;
}
