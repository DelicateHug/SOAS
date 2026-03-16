/**
 * Base webview panel with postMessage API bridge and WebSocket bridge.
 * All webview panels extend this to get auth-aware API proxying and WS management.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import { WebSocketManager } from "../api/websocket";
import { MSG, CONTEXT_KEYS } from "../constants";
import { logError, log } from "../utils/notifications";

export type PanelType =
  | "graphEditor"
  | "wikiEditor"
  | "dashboard"
  | "monitoring"
  | "incidentDetail"
  | "caseDetail"
  | "executionOutput"
  | "adminUsers"
  | "adminRoles"
  | "adminSoasVariables"
  | "adminIncidentVariables"
  | "adminFormDefinitions"
  | "adminWebhooks"
  | "adminWebhookSources"
  | "adminNormalization"
  | "adminUserSecrets"
  | "adminReviewChanges"
  | "adminSettings";

/** Active panels tracked by type+id to prevent duplicates */
const activePanels = new Map<string, BasePanel>();

/** Get the currently active graph editor panel (if any) */
export function getActiveGraphEditorPanel(): BasePanel | null {
  for (const panel of activePanels.values()) {
    if (panel.panelType === "graphEditor" && panel.isActive) {
      return panel;
    }
  }
  // Fallback: return any graph editor panel even if not focused
  for (const panel of activePanels.values()) {
    if (panel.panelType === "graphEditor") {
      return panel;
    }
  }
  return null;
}

/** Get the currently active wiki editor panel (if any) */
export function getActiveWikiEditorPanel(): BasePanel | null {
  for (const panel of activePanels.values()) {
    if (panel.panelType === "wikiEditor" && panel.isActive) {
      return panel;
    }
  }
  for (const panel of activePanels.values()) {
    if (panel.panelType === "wikiEditor") {
      return panel;
    }
  }
  return null;
}

export class BasePanel implements vscode.Disposable {
  private panel: vscode.WebviewPanel;
  private wsManager: WebSocketManager;
  private disposables: vscode.Disposable[] = [];
  private _isActive = true;
  private _graphStateResolvers: Array<(data: unknown) => void> = [];
  private _wikiStateResolvers: Array<(data: unknown) => void> = [];

  private constructor(
    extensionUri: vscode.Uri,
    readonly panelType: PanelType,
    title: string,
    private authManager: AuthManager,
    private initData?: Record<string, unknown>
  ) {
    this.panel = vscode.window.createWebviewPanel(
      `soas-${panelType}`,
      title,
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.joinPath(extensionUri, "dist", "webview"),
          vscode.Uri.joinPath(extensionUri, "resources"),
        ],
      }
    );

    this.wsManager = new WebSocketManager(() => this.authManager.getAccessToken());
    this.wsManager.setBridge(this.panel.webview);

    // Set the webview HTML
    const webviewUri = this.panel.webview.asWebviewUri(
      vscode.Uri.joinPath(extensionUri, "dist", "webview")
    );
    this.panel.webview.html = this.getHtml(webviewUri);

    // Handle messages from webview
    this.disposables.push(
      this.panel.webview.onDidReceiveMessage((msg) => this.handleMessage(msg))
    );

    // Set context key for graph editor
    if (panelType === "graphEditor") {
      vscode.commands.executeCommand("setContext", CONTEXT_KEYS.GRAPH_EDITOR_ACTIVE, true);
    }

    // Clean up on dispose
    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    // Track panel visibility for context keys
    this.disposables.push(
      this.panel.onDidChangeViewState((e) => {
        this._isActive = e.webviewPanel.active;
        if (panelType === "graphEditor") {
          vscode.commands.executeCommand(
            "setContext",
            CONTEXT_KEYS.GRAPH_EDITOR_ACTIVE,
            e.webviewPanel.active
          );
        }
      })
    );
  }

  /** Whether this panel is currently visible/active */
  get isActive(): boolean {
    return this._isActive;
  }

  /** The automation ID if this is a graph editor panel */
  get automationId(): string | undefined {
    return this.initData?.automationId as string | undefined;
  }

  /**
   * Request the current graph state from the webview.
   * Returns the VP2GraphData JSON from the graph editor store.
   */
  async requestGraphState(): Promise<unknown> {
    return new Promise<unknown>((resolve) => {
      this._graphStateResolvers.push(resolve);
      this.panel.webview.postMessage({ type: MSG.GRAPH_STATE + "-request" });

      // Timeout after 5s
      setTimeout(() => {
        const idx = this._graphStateResolvers.indexOf(resolve);
        if (idx !== -1) {
          this._graphStateResolvers.splice(idx, 1);
          resolve({ error: "Timeout requesting graph state from webview" });
        }
      }, 5000);
    });
  }

  /**
   * Request the current wiki page state from the webview.
   * Returns the wiki page title, slug, and content.
   */
  async requestWikiState(): Promise<unknown> {
    return new Promise<unknown>((resolve) => {
      this._wikiStateResolvers.push(resolve);
      this.panel.webview.postMessage({ type: MSG.WIKI_STATE + "-request" });

      setTimeout(() => {
        const idx = this._wikiStateResolvers.indexOf(resolve);
        if (idx !== -1) {
          this._wikiStateResolvers.splice(idx, 1);
          resolve({ error: "Timeout requesting wiki state from webview" });
        }
      }, 5000);
    });
  }

  /**
   * Push new graph data to the webview to load.
   */
  pushGraphData(graphData: unknown): void {
    this.panel.webview.postMessage({
      type: MSG.GRAPH_LOAD,
      data: graphData,
    });
  }

  static createOrShow(
    extensionUri: vscode.Uri,
    panelType: PanelType,
    title: string,
    authManager: AuthManager,
    initData?: Record<string, unknown>
  ): BasePanel {
    const key = `${panelType}:${JSON.stringify(initData || {})}`;

    const existing = activePanels.get(key);
    if (existing) {
      existing.panel.reveal();
      return existing;
    }

    const panel = new BasePanel(extensionUri, panelType, title, authManager, initData);
    activePanels.set(key, panel);
    panel.disposables.push({
      dispose: () => activePanels.delete(key),
    });

    return panel;
  }

  /** Broadcast dev mode change to all open webview panels */
  static broadcastDevMode(enabled: boolean): void {
    for (const panel of activePanels.values()) {
      panel.panel.webview.postMessage({
        type: "dev-mode-changed",
        enabled,
      });
    }
  }

  private async handleMessage(msg: { type: string; [key: string]: unknown }): Promise<void> {
    switch (msg.type) {
      case MSG.API_REQUEST: {
        const { requestId, method, path, body } = msg as {
          requestId: number;
          method: string;
          path: string;
          body?: unknown;
        };
        try {
          let data: unknown;
          switch (method) {
            case "GET":
              data = await apiClient.get(path);
              break;
            case "POST":
              data = await apiClient.post(path, body);
              break;
            case "PATCH":
              data = await apiClient.patch(path, body);
              break;
            case "PUT":
              data = await apiClient.put(path, body);
              break;
            case "DELETE":
              data = await apiClient.delete(path);
              break;
            default:
              throw new Error(`Unknown method: ${method}`);
          }
          this.panel.webview.postMessage({
            type: MSG.API_RESPONSE,
            requestId,
            data,
          });
        } catch (error: unknown) {
          this.panel.webview.postMessage({
            type: MSG.API_RESPONSE,
            requestId,
            error: error instanceof Error ? { error: error.message, status_code: 500 } : error,
          });
        }
        break;
      }

      case MSG.WS_OPEN:
      case MSG.WS_SEND:
      case MSG.WS_CLOSE:
        await this.wsManager.handleMessage(msg as { type: string; wsId?: string; url?: string; data?: string });
        break;

      case MSG.PANEL_READY:
        // Webview is ready, send init data
        log(`Panel "${this.panelType}" ready — sending init: ${JSON.stringify(this.initData)}`);
        this.panel.webview.postMessage({
          type: MSG.PANEL_INIT,
          panelType: this.panelType,
          data: this.initData,
        });
        // Send current dev mode state
        this.panel.webview.postMessage({
          type: "dev-mode-changed",
          enabled: apiClient.devMode,
        });
        break;

      case MSG.GRAPH_STATE + "-response": {
        // Webview is responding with the current graph state
        const resolver = this._graphStateResolvers.shift();
        if (resolver) {
          resolver(msg.data);
        }
        break;
      }

      case MSG.WIKI_STATE + "-response": {
        const wikiResolver = this._wikiStateResolvers.shift();
        if (wikiResolver) {
          wikiResolver(msg.data);
        }
        break;
      }

      default:
        log(`Unknown message type from webview: ${msg.type}`);
    }
  }

  private getHtml(webviewUri: vscode.Uri): string {
    const nonce = getNonce();

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${this.panel.webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'; connect-src ${this.panel.webview.cspSource}; img-src ${this.panel.webview.cspSource} data:; font-src ${this.panel.webview.cspSource};">
  <link rel="stylesheet" href="${webviewUri}/index.css">
</head>
<body data-panel-type="${this.panelType}">
  <div id="root"></div>
  <script nonce="${nonce}" src="${webviewUri}/index.js"></script>
</body>
</html>`;
  }

  dispose(): void {
    if (this.panelType === "graphEditor") {
      vscode.commands.executeCommand("setContext", CONTEXT_KEYS.GRAPH_EDITOR_ACTIVE, false);
    }
    this.wsManager.dispose();
    this.disposables.forEach((d) => d.dispose());
    this.panel.dispose();
  }
}

function getNonce(): string {
  let text = "";
  const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}
