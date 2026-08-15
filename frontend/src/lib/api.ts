/**
 * API client with auth token management, auto-refresh, and HMAC request signing.
 *
 * Two authentication modes are supported:
 *  - Cookie + HMAC (preferred for browsers): set on login, the cookie carries
 *    `<session_id>.<session_key>`. The session key is held in memory and used to HMAC-
 *    sign every request. IP-bound, 6h TTL, revoked on logout or IP mismatch.
 *  - Bearer JWT (legacy): kept so existing tests/admin tooling still work. Will be
 *    phased out once all UI flows have moved to cookie auth.
 */

const API_BASE = "/api/v1";

interface ApiError {
  error: string;
  detail?: string;
  status_code: number;
}

/** Paths exempt from HMAC signing because the client doesn't yet have a key. */
const UNSIGNED_PATHS = [
  "/auth/session/bootstrap",
  "/auth/login",
  "/auth/register",
  "/auth/providers",
  "/auth/registration-open",
  "/auth/oidc/start",
  "/auth/oidc/callback",
  "/auth/mfa/verify",
  // /auth/refresh still exists for legacy bearer clients; the SPA does not call it,
  // but listing it here keeps anything that does call it from getting a "no sessionKey
  // loaded" redirect-to-login.
  "/auth/refresh",
];

/** Convert an ArrayBuffer to a lower-case hex string. */
function bufToHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Base64url-decode the session key delivered by /auth/session/bootstrap into raw bytes. */
function decodeSessionKey(b64: string): Uint8Array {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const std = (b64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(std);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Sort query parameters alphabetically so client and server agree on order. */
function canonicalQuery(search: string): string {
  if (!search) return "";
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const entries: [string, string][] = [];
  params.forEach((v, k) => entries.push([k, v]));
  entries.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : 1));
  return entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
}

/**
 * 5-minute heartbeat interval. Matches the server's IDLE_TIMEOUT_MINUTES=30 — the
 * client can miss 6 in a row before the server kills the session. Long enough that
 * sleeping/locking a laptop for a coffee break is fine, short enough that a walked-
 * away terminal becomes unusable within half an hour.
 */
const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000;

class ApiClient {
  private _devMode: boolean = false;

  // Session-key auth state (cookie path). Held in memory only — page reload re-bootstraps.
  // The cookie itself is also session-scope (no max_age), so closing the browser kills
  // the whole session. There is no refresh: 401 -> /login.
  private sessionKey: CryptoKey | null = null;
  private sessionKeyRaw: Uint8Array | null = null;
  private bootstrapPromise: Promise<boolean> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  // Kept as no-op stubs so existing call sites (authStore.setTokens, etc.) keep compiling.
  // Browser auth is cookie-only; these methods no longer persist anything.
  private onTokensChanged: ((accessToken: string, refreshToken: string) => void) | null = null;

  constructor() {
    this._devMode = localStorage.getItem("dev_mode") === "true";
    // Clear any stale JWTs left over from earlier deployments.
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  get devMode(): boolean {
    return this._devMode;
  }

  setDevMode(enabled: boolean) {
    this._devMode = enabled;
    if (enabled) {
      localStorage.setItem("dev_mode", "true");
    } else {
      localStorage.removeItem("dev_mode");
    }
  }

  setOnTokensChanged(callback: ((accessToken: string, refreshToken: string) => void) | null) {
    this.onTokensChanged = callback;
  }

  /** @deprecated Browser auth uses the soas_session cookie, not a Bearer JWT. Always null. */
  getAccessToken(): string | null {
    return null;
  }

  /** @deprecated Login no longer stores tokens in JS; the cookie is the only credential.
   * Kept so callers that pass through the JWT response field don't need to be rewritten. */
  setTokens(access: string, _refresh: string) {
    this.onTokensChanged?.(access, _refresh);
  }

  clearTokens() {
    this.sessionKey = null;
    this.sessionKeyRaw = null;
    this.stopHeartbeat();
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("must_reset_password");
  }

  /**
   * Start sending GET /auth/session/heartbeat every 5 minutes. The server-side idle
   * timeout is 30 minutes, so missing one or two heartbeats is fine; missing six is
   * fatal. Idempotent — calling it twice is a no-op.
   */
  private startHeartbeat() {
    if (this.heartbeatTimer || typeof window === "undefined") return;
    this.heartbeatTimer = setInterval(() => {
      // Fire-and-forget. If the heartbeat call returns 401 the api.request() handler
      // will already redirect to /login, so we don't need to do anything here.
      this.request("/auth/session/heartbeat").catch(() => {});
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  get isAuthenticated(): boolean {
    return this.sessionKey !== null;
  }

  /** Fetch the session HMAC key after login. Idempotent + de-duped under concurrent calls. */
  async bootstrapSession(): Promise<boolean> {
    if (this.sessionKey) return true;
    if (this.bootstrapPromise) return this.bootstrapPromise;
    this.bootstrapPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/session/bootstrap`, {
          method: "GET",
          credentials: "include",
        });
        if (!res.ok) return false;
        const data = await res.json();
        const raw = decodeSessionKey(data.session_key as string);
        this.sessionKeyRaw = raw;
        this.sessionKey = await crypto.subtle.importKey(
          "raw",
          raw,
          { name: "HMAC", hash: "SHA-256" },
          false,
          ["sign"],
        );
        this.startHeartbeat();
        return true;
      } catch (e) {
        console.warn("[soas-auth] bootstrap failed:", e);
        return false;
      } finally {
        this.bootstrapPromise = null;
      }
    })();
    return this.bootstrapPromise;
  }

  /** Compute the HMAC headers for a request. Returns {} if no session key is loaded. */
  private async signHeaders(method: string, path: string, query: string, body: BodyInit | undefined): Promise<Record<string, string>> {
    if (!this.sessionKey || !this.sessionKeyRaw) {
      console.warn("[soas-auth] signHeaders: no sessionKey loaded for", method, path);
      return {};
    }
    const timestamp = Math.floor(Date.now() / 1000).toString();

    // Compute SHA256 of the body. fetch may pass FormData, ArrayBuffer, string, etc. We
    // only sign the raw bytes the server will receive — for JSON strings that's the
    // UTF-8 encoding; for FormData we skip body hashing (set to hash of empty) since the
    // browser serialises the multipart on send and the server's signature check for
    // uploads is disabled in this revision.
    let bodyBytes: Uint8Array;
    if (!body) {
      bodyBytes = new Uint8Array(0);
    } else if (typeof body === "string") {
      bodyBytes = new TextEncoder().encode(body);
    } else if (body instanceof ArrayBuffer) {
      bodyBytes = new Uint8Array(body);
    } else if (body instanceof Uint8Array) {
      bodyBytes = body;
    } else {
      bodyBytes = new Uint8Array(0); // FormData / Blob — fall back to empty hash
    }
    const bodyHash = bufToHex(await crypto.subtle.digest("SHA-256", bodyBytes));

    const canonical = [method.toUpperCase(), path, canonicalQuery(query), timestamp, bodyHash].join("\n");
    const sig = await crypto.subtle.sign("HMAC", this.sessionKey, new TextEncoder().encode(canonical));
    const sigHex = bufToHex(sig);
    return {
      "X-SOAS-Timestamp": timestamp,
      "X-SOAS-Signature": sigHex,
    };
  }

  async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    const method = (options.method || "GET").toUpperCase();
    // Split path into pathname + query string for canonical signing.
    const [pathname, query = ""] = path.split("?", 2);

    // Cookie + HMAC is the only browser auth flow. No Bearer header is sent — the JWT
    // returned by /auth/login is intentionally ignored. There is no refresh: when the
    // session expires (browser close OR the 6h server-side TTL, whichever comes first),
    // the user must log in again.
    if (this._devMode) {
      headers["X-Dev-Mode"] = "true";
    }

    // Sign with the session HMAC key unless this is one of the bootstrap/auth paths.
    const unsigned = UNSIGNED_PATHS.some((p) => pathname.startsWith(p));
    if (!unsigned) {
      // If a bootstrap is in flight (page just loaded; we haven't installed the key yet),
      // wait for it before signing. Avoids the first-request-after-reload race where the
      // singleton has no key cached and we'd send an unsigned request.
      if (!this.sessionKey) {
        if (!this.bootstrapPromise) {
          // No bootstrap running and no key — try once. This covers tabs whose store
          // initialiser fired bootstrap before the cookie was set, or modules that
          // call api.get() before the store mounts.
          this.bootstrapSession().catch(() => {});
        }
        if (this.bootstrapPromise) {
          await this.bootstrapPromise;
        }
      }
      // Still no key after the bootstrap attempt = effectively not authenticated.
      // Skip the doomed unsigned request entirely and send the user to /login.
      if (!this.sessionKey) {
        this.clearTokens();
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = "/login?reason=no_session";
        }
        throw new Error("Not authenticated");
      }
      const sigHeaders = await this.signHeaders(method, `${API_BASE}${pathname}`, query, options.body as BodyInit | undefined);
      Object.assign(headers, sigHeaders);
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });

    // Any 401 on a signed (non-auth) endpoint means the session is dead. No refresh —
    // user re-authenticates by visiting /login.
    if (res.status === 401 && !unsigned) {
      this.clearTokens();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        const reason = res.headers.get("x-cae-revoked") === "true" ? "revoked" : "expired";
        window.location.href = `/login?reason=${reason}`;
      }
      throw new Error("Session expired");
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
    if (this._devMode) {
      headers["X-Dev-Mode"] = "true";
    }

    // FormData uploads still carry the cookie + HMAC headers (we hash an empty body —
    // the server-side upload route is exempt from body-hash matching in this revision).
    const [pathname, query = ""] = path.split("?", 2);

    // Make sure we have the session key before signing (same race fix as request()).
    if (!this.sessionKey) {
      if (!this.bootstrapPromise) {
        this.bootstrapSession().catch(() => {});
      }
      if (this.bootstrapPromise) {
        await this.bootstrapPromise;
      }
    }
    if (!this.sessionKey) {
      this.clearTokens();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login?reason=no_session";
      }
      throw new Error("Not authenticated");
    }
    const sigHeaders = await this.signHeaders("POST", `${API_BASE}${pathname}`, query, undefined);
    Object.assign(headers, sigHeaders);

    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: formData,
      credentials: "include",
    });

    // No refresh fallback: a 401 means the cookie/session is dead. Bounce to login.
    if (res.status === 401) {
      this.clearTokens();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login?reason=expired";
      }
      throw new Error("Session expired");
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
