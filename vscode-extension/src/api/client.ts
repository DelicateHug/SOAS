/**
 * Node.js API client for SOAS backend.
 * Mirrors the frontend ApiClient pattern but uses Node fetch + SecretStorage for tokens.
 */

import { getServerUrl } from "../utils/config";
import { log, logError } from "../utils/notifications";

interface ApiError {
  error: string;
  detail?: string;
  status_code: number;
}

/** Auth paths that should never trigger token refresh on 401. */
const AUTH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

export type TokenProvider = {
  getAccessToken(): Promise<string | undefined>;
  getRefreshToken(): Promise<string | undefined>;
  setTokens(access: string, refresh: string): Promise<void>;
  clearTokens(): Promise<void>;
  onSessionExpired(): void;
};

export class ApiClient {
  private refreshPromise: Promise<boolean> | null = null;
  private tokenProvider: TokenProvider | null = null;
  private _devMode = false;

  setTokenProvider(provider: TokenProvider): void {
    this.tokenProvider = provider;
  }

  get devMode(): boolean {
    return this._devMode;
  }

  setDevMode(enabled: boolean): void {
    this._devMode = enabled;
  }

  private getBaseUrl(): string {
    return getServerUrl() + "/api/v1";
  }

  private async refreshAccessToken(): Promise<boolean> {
    if (!this.tokenProvider) return false;

    const refreshToken = await this.tokenProvider.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${this.getBaseUrl()}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        await this.tokenProvider.clearTokens();
        return false;
      }

      const data = await res.json() as { access_token: string; refresh_token: string };
      await this.tokenProvider.setTokens(data.access_token, data.refresh_token);
      log("Token refreshed successfully");
      return true;
    } catch (err) {
      logError("Token refresh failed", err);
      await this.tokenProvider.clearTokens();
      return false;
    }
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.tokenProvider) {
      const token = await this.tokenProvider.getAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    if (this._devMode) {
      headers["X-Dev-Mode"] = "true";
    }

    let res = await fetch(`${this.getBaseUrl()}${path}`, { ...options, headers });

    // If 401 on a non-auth endpoint, try refreshing the token
    const isAuthPath = AUTH_PATHS.some((p) => path.startsWith(p));
    if (res.status === 401 && this.tokenProvider && !isAuthPath) {
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshAccessToken();
      }
      const refreshed = await this.refreshPromise;
      this.refreshPromise = null;

      if (refreshed) {
        const token = await this.tokenProvider.getAccessToken();
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        res = await fetch(`${this.getBaseUrl()}${path}`, { ...options, headers });
      } else {
        this.tokenProvider.onSessionExpired();
        throw new Error("Session expired");
      }
    }

    if (!res.ok) {
      const error: ApiError = await res.json().catch(() => ({
        error: "Unknown error",
        status_code: res.status,
      }));
      throw error;
    }

    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }

  put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  delete(path: string): Promise<unknown> {
    return this.request(path, { method: "DELETE" });
  }
}

/** Singleton API client instance */
export const apiClient = new ApiClient();
