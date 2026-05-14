// Thin HTTP wrapper around the SOAS backend, scoped to this MCP server's needs.
// One client per process; the bearer token is loaded once at startup and refreshed only
// on demand (e.g. via `reloadToken()`).
//
// Errors throw a SoasApiError with status + body so tool handlers can return useful
// diagnostics to the MCP client instead of opaque "fetch failed".

import { readFile, watch } from "node:fs/promises";

export class SoasApiError extends Error {
  constructor(status, message, body) {
    super(`SOAS API ${status}: ${message}`);
    this.name = "SoasApiError";
    this.status = status;
    this.body = body;
  }
}

export class SoasClient {
  constructor({ baseUrl, getToken, embeddingsBaseUrl }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.embeddingsBaseUrl = (embeddingsBaseUrl || "").replace(/\/$/, "");
    this._getToken = getToken;
  }

  async _headers(extra = {}) {
    const token = await this._getToken();
    return {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...extra,
    };
  }

  async _request(method, path, { query, body } = {}) {
    let url = `${this.baseUrl}${path}`;
    if (query && Object.keys(query).length > 0) {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(query)) {
        if (v === undefined || v === null) continue;
        if (Array.isArray(v)) v.forEach((item) => params.append(k, String(item)));
        else params.set(k, String(v));
      }
      const qs = params.toString();
      if (qs) url += `?${qs}`;
    }

    const init = { method, headers: await this._headers() };
    if (body !== undefined) init.body = JSON.stringify(body);

    const res = await fetch(url, init);
    const text = await res.text();
    let parsed;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = text;
    }
    if (!res.ok) {
      const message = (parsed && parsed.detail) || res.statusText || "request failed";
      throw new SoasApiError(res.status, message, parsed);
    }
    return parsed;
  }

  get(path, query) {
    return this._request("GET", path, { query });
  }
  post(path, body) {
    return this._request("POST", path, { body });
  }
  patch(path, body) {
    return this._request("PATCH", path, { body });
  }
  put(path, body) {
    return this._request("PUT", path, { body });
  }
  del(path) {
    return this._request("DELETE", path);
  }

  // ─── Embeddings sidecar ────────────────────────────────────────────────
  // Exposed so the MCP client can compute query similarity against arbitrary text
  // even outside the wiki RAG path (e.g. ad-hoc dedup of incidents).
  async embed(texts, { normalize = true } = {}) {
    if (!this.embeddingsBaseUrl) {
      throw new Error("Embeddings service URL not configured");
    }
    const res = await fetch(`${this.embeddingsBaseUrl}/embed`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ texts, normalize }),
    });
    if (!res.ok) {
      const body = await res.text();
      throw new SoasApiError(res.status, "Embeddings call failed", body);
    }
    return res.json();
  }
}

/**
 * Resolve a bearer token from either an env var (highest priority for CI) or a
 * mounted file. Watches the file for changes and reloads on update so token
 * rotation doesn't require a container restart.
 */
export async function makeTokenProvider({ envVar = "SOAS_TOKEN", file = "" } = {}) {
  let cached = process.env[envVar] || "";
  let watching = false;

  async function loadFromFile() {
    if (!file) return "";
    try {
      const text = await readFile(file, "utf8");
      return text.trim();
    } catch (err) {
      if (err.code === "ENOENT") return "";
      throw err;
    }
  }

  if (!cached && file) {
    cached = await loadFromFile();
  }

  // Watch the file in the background; if it changes we pick up the new value next
  // request. We don't await this — a watch failure shouldn't block startup.
  if (file && !watching) {
    watching = true;
    (async () => {
      try {
        const watcher = watch(file);
        for await (const _ of watcher) {
          try {
            const next = await loadFromFile();
            if (next) cached = next;
          } catch {
            // ignore — keep the previous value
          }
        }
      } catch {
        // watch may not be supported on the underlying FS; that's fine — `reload`
        // can be called manually if needed.
      }
    })();
  }

  return {
    async get() {
      if (cached) return cached;
      cached = await loadFromFile();
      if (!cached) {
        throw new Error(
          `No SOAS service token available. Set $${envVar} or mount one at ${file}.`,
        );
      }
      return cached;
    },
    async reload() {
      const next = (process.env[envVar] || (await loadFromFile())).trim();
      if (next) cached = next;
      return cached;
    },
  };
}
