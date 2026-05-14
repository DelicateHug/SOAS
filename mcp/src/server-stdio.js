// Stdio variant of the SOAS MCP server. Same tools, same client; just a different
// transport. Useful for Claude Code's classic .mcp.json `command` shape where the
// editor spawns the process directly.
//
// The token is read from $SOAS_TOKEN or $SOAS_TOKEN_FILE just like the HTTP variant —
// the calling editor is responsible for setting one of those before launching this.

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { SoasClient, makeTokenProvider } from "./soas-client.js";
import { registerTools } from "./tools.js";

const SOAS_API_URL = process.env.SOAS_API_URL || "http://localhost:8000/api/v1";
const EMBEDDINGS_URL = process.env.EMBEDDING_SERVICE_URL || "http://localhost:8200";
const TOKEN_FILE = process.env.SOAS_TOKEN_FILE || "";

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

  const server = new McpServer(
    { name: "soas", version: "1.0.0" },
    { capabilities: { tools: {} } },
  );
  registerTools(server, client);

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  // stderr only — stdout is the MCP wire.
  console.error("[soas-mcp/stdio] fatal:", err);
  process.exit(1);
});
