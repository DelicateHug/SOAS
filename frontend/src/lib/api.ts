/**
 * API client with auth token management and auto-refresh.
 */

const API_BASE = "/api/v1";

interface ApiError {
  error: string;
  detail?: string;
  status_code: number;
}

/** Auth paths that should never trigger token refresh on 401. */
const AUTH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<boolean> | null = null;
  private onTokensChanged: ((accessToken: string, refreshToken: string) => void) | null = null;

  constructor() {
    this.accessToken = localStorage.getItem("access_token");
    this.refreshToken = localStorage.getItem("refresh_token");
  }

  setOnTokensChanged(callback: ((accessToken: string, refreshToken: string) => void) | null) {
    this.onTokensChanged = callback;
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setTokens(access: string, refresh: string) {
    this.accessToken = access;
    this.refreshToken = refresh;
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    this.onTokensChanged?.(access, refresh);
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  get isAuthenticated(): boolean {
    return this.accessToken !== null;
  }

  private async refreshAccessToken(): Promise<boolean> {
    if (!this.refreshToken) return false;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });

      if (!res.ok) {
        this.clearTokens();
        return false;
      }

      const data = await res.json();
      this.setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      this.clearTokens();
      return false;
    }
  }

  async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    let res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    // If 401 on a non-auth endpoint, try refreshing the token
    const isAuthPath = AUTH_PATHS.some((p) => path.startsWith(p));
    if (res.status === 401 && this.refreshToken && !isAuthPath) {
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshAccessToken();
      }
      const refreshed = await this.refreshPromise;
      this.refreshPromise = null;

      if (refreshed) {
        headers["Authorization"] = `Bearer ${this.accessToken}`;
        res = await fetch(`${API_BASE}${path}`, { ...options, headers });
      } else {
        window.location.href = "/login";
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
    return res.json();
  }

  get<T>(path: string) {
    return this.request<T>(path);
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  patch<T>(path: string, body: unknown) {
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }

  put<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  delete(path: string) {
    return this.request(path, { method: "DELETE" });
  }

  async upload<T>(path: string, formData: FormData): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    let res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (res.status === 401 && this.refreshToken) {
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshAccessToken();
      }
      const refreshed = await this.refreshPromise;
      this.refreshPromise = null;

      if (refreshed) {
        headers["Authorization"] = `Bearer ${this.accessToken}`;
        res = await fetch(`${API_BASE}${path}`, {
          method: "POST",
          headers,
          body: formData,
        });
      } else {
        window.location.href = "/login";
        throw new Error("Session expired");
      }
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({
        error: "Unknown error",
        status_code: res.status,
      }));
      throw error;
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }
}

export const api = new ApiClient();
