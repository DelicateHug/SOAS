/**
 * API client bridge for webview.
 * Drop-in replacement for frontend/src/lib/api.ts — routes all HTTP requests
 * through the extension host via postMessage.
 *
 * Exports the same `api` singleton with the same interface.
 */

import { getVsCodeApi } from "../vscode";

interface ApiError {
  error: string;
  detail?: string;
  status_code: number;
}

let requestId = 0;
const pending = new Map<number, { resolve: (data: unknown) => void; reject: (error: unknown) => void }>();

// Listeners for dev mode changes (used by useDeploymentMode via useSyncExternalStore)
const devModeListeners = new Set<() => void>();

// Listen for API responses and dev-mode updates from extension host
window.addEventListener("message", (event) => {
  const msg = event.data;
  if (msg.type === "api-response" && typeof msg.requestId === "number") {
    const p = pending.get(msg.requestId);
    if (p) {
      pending.delete(msg.requestId);
      if (msg.error) {
        p.reject(msg.error);
      } else {
        p.resolve(msg.data);
      }
    }
  } else if (msg.type === "dev-mode-changed") {
    api.setDevMode(msg.enabled);
  }
});

function apiRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    const id = ++requestId;
    pending.set(id, {
      resolve: resolve as (data: unknown) => void,
      reject,
    });
    getVsCodeApi().postMessage({
      type: "api-request",
      requestId: id,
      method,
      path,
      body,
    });
  });
}

/**
 * API client that mirrors the frontend ApiClient interface.
 * All methods route through the extension host via postMessage.
 */
class WebviewApiClient {
  // These are no-ops in the webview — auth is handled by the extension host
  private _devMode = false;

  get devMode(): boolean {
    return this._devMode;
  }

  setDevMode(enabled: boolean) {
    this._devMode = enabled;
    // Notify useDeploymentMode subscribers
    devModeListeners.forEach((l) => l());
  }

  setOnTokensChanged(_callback: ((accessToken: string, refreshToken: string) => void) | null) {
    // No-op: token management is handled by the extension host
  }

  getAccessToken(): string | null {
    return null; // Tokens are managed by the extension host
  }

  setTokens(_access: string, _refresh: string) {
    // No-op
  }

  clearTokens() {
    // No-op
  }

  get isAuthenticated(): boolean {
    return true; // If the webview is open, we're authenticated
  }

  get<T>(path: string): Promise<T> {
    return apiRequest<T>("GET", path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return apiRequest<T>("POST", path, body);
  }

  patch<T>(path: string, body: unknown): Promise<T> {
    return apiRequest<T>("PATCH", path, body);
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return apiRequest<T>("PUT", path, body);
  }

  delete(path: string): Promise<unknown> {
    return apiRequest("DELETE", path);
  }

  async upload<T>(path: string, _formData: FormData): Promise<T> {
    // File uploads need special handling — for now, throw
    throw new Error("File uploads are not yet supported in the VSCode extension webview");
  }
}

export const api = new WebviewApiClient();
