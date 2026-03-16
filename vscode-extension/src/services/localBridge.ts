/**
 * Local HTTP bridge server.
 * Exposes SOAS tools to external processes (e.g., MCP servers for Claude Code).
 * Runs on localhost:19542, proxies API calls with auth, and bridges graph state.
 */

import * as http from "http";
import { apiClient } from "../api/client";
import { getActiveGraphEditorPanel, getActiveWikiEditorPanel } from "../panels/basePanel";
import { log, logError } from "../utils/notifications";

const BRIDGE_PORT = 19542;

let server: http.Server | null = null;
let refreshCallback: (() => void) | null = null;

/** Register a callback to refresh tree views after bridge mutations (POST/PATCH/DELETE on /api/) */
export function onBridgeMutation(cb: () => void): void {
  refreshCallback = cb;
}

export function startLocalBridge(): void {
  if (server) return;

  server = http.createServer(async (req, res) => {
    // CORS for local access
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    try {
      const url = new URL(req.url || "/", `http://localhost:${BRIDGE_PORT}`);
      const path = url.pathname;

      // Health check
      if (path === "/health") {
        sendJson(res, 200, { status: "ok", bridge: "soas-extension" });
        return;
      }

      // Graph state — get current graph from active editor
      if (path === "/graph-state" && req.method === "GET") {
        const panel = getActiveGraphEditorPanel();
        if (!panel) {
          sendJson(res, 404, { error: "No graph editor is currently open" });
          return;
        }
        const state = await panel.requestGraphState();
        sendJson(res, 200, state);
        return;
      }

      // Wiki state — get current wiki page from active editor
      if (path === "/wiki-state" && req.method === "GET") {
        const wikiPanel = getActiveWikiEditorPanel();
        if (!wikiPanel) {
          sendJson(res, 404, { error: "No wiki editor is currently open" });
          return;
        }
        const state = await wikiPanel.requestWikiState();
        sendJson(res, 200, state);
        return;
      }

      // Graph load — push graph data to active editor
      if (path === "/graph-load" && req.method === "POST") {
        const panel = getActiveGraphEditorPanel();
        if (!panel) {
          sendJson(res, 404, { error: "No graph editor is currently open" });
          return;
        }
        const body = await readBody(req);
        const data = JSON.parse(body);
        panel.pushGraphData(data.graphData || data);
        sendJson(res, 200, { success: true, message: "Graph updated in editor" });
        return;
      }

      // Proxy API calls to SOAS backend
      if (path.startsWith("/api/")) {
        const apiPath = path.replace(/^\/api/, "");
        const body = req.method !== "GET" ? await readBody(req) : undefined;

        let result: unknown;
        switch (req.method) {
          case "GET":
            result = await apiClient.get(apiPath + url.search);
            break;
          case "POST":
            result = await apiClient.post(apiPath, body ? JSON.parse(body) : undefined);
            break;
          case "PUT":
            result = await apiClient.put(apiPath, body ? JSON.parse(body) : undefined);
            break;
          case "PATCH":
            result = await apiClient.patch(apiPath, body ? JSON.parse(body) : undefined);
            break;
          case "DELETE":
            result = await apiClient.delete(apiPath);
            break;
          default:
            sendJson(res, 405, { error: `Method ${req.method} not allowed` });
            return;
        }
        sendJson(res, 200, result);

        // Trigger tree refresh after mutations
        if (req.method !== "GET" && refreshCallback) {
          refreshCallback();
        }
        return;
      }

      sendJson(res, 404, { error: "Not found" });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      logError("Bridge request failed", err);
      sendJson(res, 500, { error: message });
    }
  });

  server.listen(BRIDGE_PORT, "127.0.0.1", () => {
    log(`SOAS bridge server listening on http://127.0.0.1:${BRIDGE_PORT}`);
  });

  server.on("error", (err: NodeJS.ErrnoException) => {
    if (err.code === "EADDRINUSE") {
      log(`Bridge port ${BRIDGE_PORT} already in use — bridge may already be running`);
    } else {
      logError("Bridge server error", err);
    }
    server = null;
  });
}

export function stopLocalBridge(): void {
  if (server) {
    server.close();
    server = null;
    log("SOAS bridge server stopped");
  }
}

function sendJson(res: http.ServerResponse, status: number, data: unknown): void {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    req.on("error", reject);
  });
}
