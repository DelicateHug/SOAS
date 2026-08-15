// SOAS MCP server — streamable HTTP transport.
//
// Why streamable HTTP and not SSE? The MCP spec deprecated standalone SSE in favour of a
// single bidirectional HTTP endpoint that supports both POST (client→server) and GET
// (server→client streaming). The SDK ships StreamableHTTPServerTransport for this.
//
// One transport instance per session. Sessions are identified by a header the SDK manages
// (Mcp-Session-Id). We hold open transports in a Map keyed by session id and clean them up
// when the underlying request closes.

import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import https from "node:https";

import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";

import { SoasClient, makeTokenProvider } from "./soas-client.js";
import { registerTools } from "./tools.js";
import { startHeartbeat } from "./heartbeat.js";

const PORT = parseInt(process.env.MCP_HTTP_PORT || "8765", 10);
const SOAS_API_URL = process.env.SOAS_API_URL || "https://backend:8000/api/v1";
const EMBEDDINGS_URL = process.env.EMBEDDING_SERVICE_URL || "https://embeddings:8200";
const TOKEN_FILE = process.env.SOAS_TOKEN_FILE || "/run/secrets/mcp_token";
const MTLS_DIR = process.env.MTLS_DIR || "/run/mtls";

// Optional bearer that the MCP *client* must present to call the *MCP* server.
// This is distinct from the SOAS service token (used to call SOAS itself). When unset,
// we accept any local connection — appropriate for the default Docker network deployment
// where the port isn't published to the host. When set, every MCP request must include
// `Authorization: Bearer <MCP_SERVER_TOKEN>`.
const MCP_SERVER_TOKEN = process.env.MCP_SERVER_TOKEN || "";

async function main() {
  const tokenProvider = await makeTokenProvider({
    envVar: "SOAS_TOKEN",
    file: TOKEN_FILE,
  });

  const client = new SoasClient({
    baseUrl: SOAS_API_URL,
    embeddingsBaseUrl: EMBEDDINGS_URL,
    getToken: () => tokenProvider.get(),
  });

  const app = express();
  app.use(express.json({ limit: "4mb" }));

  app.get("/healthz", (_req, res) => {
    res.json({ ok: true, soas: SOAS_API_URL });
  });

  // Session map. Each MCP session gets its own transport + server pairing.
  const transports = new Map();

  function authzGuard(req, res) {
    if (!MCP_SERVER_TOKEN) return true;
    const auth = req.header("authorization") || "";
    if (auth !== `Bearer ${MCP_SERVER_TOKEN}`) {
      res.status(401).json({ error: "Unauthorized: invalid MCP server token" });
      return false;
    }
    return true;
  }

  // Single endpoint for the streamable transport. The SDK handles the protocol; we just
  // route requests to the right transport based on Mcp-Session-Id.
  app.all("/mcp", async (req, res) => {
    if (!authzGuard(req, res)) return;

    // On-behalf-of header: when present, every SOAS backend call made while handling this
    // request will carry X-SOAS-On-Behalf-Of, so the backend can scope permissions to the
    // calling analyst's tier rather than the shared MCP service-token's roles.
    const obo = req.header("x-soas-on-behalf-of") || null;
    client.setOnBehalfOf(obo);
    res.on("finish", () => client.setOnBehalfOf(null));
    res.on("close", () => client.setOnBehalfOf(null));

    const sessionId = req.header("mcp-session-id");
    let transport;

    if (sessionId && transports.has(sessionId)) {
      transport = transports.get(sessionId);
    } else if (req.method === "POST" && isInitializeRequest(req.body)) {
      // First-time init: create a fresh transport + MCP server, register tools, and
      // remember the session for subsequent requests.
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (id) => transports.set(id, transport),
      });

      transport.onclose = () => {
        if (transport.sessionId) transports.delete(transport.sessionId);
      };

      const server = new McpServer(
        { name: "soas", version: "1.0.0" },
        { capabilities: { tools: {} } },
      );
      registerTools(server, client);
      await server.connect(transport);
    } else {
      res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Bad Request: missing or invalid session" },
        id: null,
      });
      return;
    }

    await transport.handleRequest(req, res, req.body);
  });

  // Convenience: a direct introspection endpoint to confirm tool wiring without going
  // through the MCP handshake. Useful for `start.ps1` / curl smoke-checks.
  app.get("/tools", async (_req, res) => {
    if (!authzGuard(_req, res)) return;
    const fakeServer = new McpServer({ name: "soas-introspect", version: "1.0.0" });
    registerTools(fakeServer, client);
    // The SDK doesn't surface a public list — fall back to the toolHandlers map. The
    // shape is implementation-detail of the SDK but stable enough for diagnostics.
    const t = fakeServer._registeredTools || fakeServer.toolHandlers || {};
    const names = Object.keys(t).sort();
    res.json({ count: names.length, tools: names });
  });

  // Phase 11.1: heartbeat into the SOAS agents registry so the MCP
  // instance shows up in the Agents tab alongside the Python services.
  startHeartbeat({ apiUrl: SOAS_API_URL });

  // mTLS: serve HTTPS and require any peer (proxy, backend, worker) to present a
  // client cert signed by the SOAS internal CA. The MCP_SERVER_TOKEN bearer is still
  // enforced on top — defence in depth.
  const tlsOpts = {
    key: readFileSync(`${MTLS_DIR}/mcp/server.key`),
    cert: readFileSync(`${MTLS_DIR}/mcp/server.crt`),
    ca: readFileSync(`${MTLS_DIR}/ca/ca.crt`),
    requestCert: true,
    rejectUnauthorized: true,
  };
  https.createServer(tlsOpts, app).listen(PORT, () => {
    console.log(`[soas-mcp] streamable-https (mTLS) listening on :${PORT}`);
    console.log(`[soas-mcp] backend: ${SOAS_API_URL}`);
    console.log(`[soas-mcp] embeddings: ${EMBEDDINGS_URL}`);
    if (MCP_SERVER_TOKEN) {
      console.log("[soas-mcp] MCP_SERVER_TOKEN set — clients must also present a bearer.");
    }
  });
}

main().catch((err) => {
  console.error("[soas-mcp] fatal:", err);
  process.exit(1);
});
