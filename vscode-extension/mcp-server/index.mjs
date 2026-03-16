#!/usr/bin/env node
/**
 * SOAS MCP Server for Claude Code.
 * Bridges Claude Code to the SOAS extension via its local HTTP bridge (port 19542).
 * All API calls and graph operations go through the extension's bridge server,
 * which handles authentication and webview communication.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const BRIDGE_URL = process.env.SOAS_BRIDGE_URL || "http://127.0.0.1:19542";

// --- Helper: call the extension bridge ---

async function bridgeGet(path) {
  const res = await fetch(`${BRIDGE_URL}${path}`);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Bridge ${path}: ${res.status} ${body}`);
  }
  return res.json();
}

async function bridgePost(path, body) {
  const res = await fetch(`${BRIDGE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Bridge POST ${path}: ${res.status} ${text}`);
  }
  return res.json();
}

async function bridgePatch(path, body) {
  const res = await fetch(`${BRIDGE_URL}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Bridge PATCH ${path}: ${res.status} ${text}`);
  }
  return res.json();
}

async function bridgeDelete(path) {
  const res = await fetch(`${BRIDGE_URL}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Bridge DELETE ${path}: ${res.status} ${text}`);
  }
  return res.json();
}

// --- MCP Server setup ---

const server = new McpServer({
  name: "soas",
  version: "1.0.0",
});

// ---- Tools ----

server.tool(
  "soas_list_incidents",
  "List incidents from SOAS, optionally filtered by severity or status",
  {
    severity: z.enum(["critical", "high", "medium", "low", "informational"]).optional(),
    status: z.string().optional(),
    page: z.number().default(1),
  },
  async ({ severity, status, page }) => {
    let url = `/api/incidents?per_page=20&page=${page}`;
    if (severity) url += `&severity=${severity}`;
    if (status) url += `&status=${status}`;
    const result = await bridgeGet(url);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_get_incident",
  "Get detailed information about a specific incident including timeline",
  {
    incidentId: z.string().describe("The incident UUID"),
  },
  async ({ incidentId }) => {
    const [incident, timeline] = await Promise.all([
      bridgeGet(`/api/incidents/${incidentId}`),
      bridgeGet(`/api/incidents/${incidentId}/timeline`),
    ]);
    return { content: [{ type: "text", text: JSON.stringify({ incident, timeline }, null, 2) }] };
  }
);

server.tool(
  "soas_list_automations",
  "List automations from SOAS",
  {
    status: z.enum(["draft", "active", "disabled", "archived"]).optional(),
    page: z.number().default(1),
  },
  async ({ status, page }) => {
    let url = `/api/automations?per_page=20&page=${page}`;
    if (status) url += `&status=${status}`;
    const result = await bridgeGet(url);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_get_node_catalog",
  "Get the full catalog of available node types for building visual automations. Each node has a type, category, inputs, outputs, and configurable properties.",
  {},
  async () => {
    const result = await bridgeGet("/api/graph-editor/node-catalog");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_get_automation_graph",
  "Get the graph data (nodes and connections) for a specific automation by ID",
  {
    automationId: z.string().describe("The automation UUID"),
  },
  async ({ automationId }) => {
    const result = await bridgeGet(`/api/automations/${automationId}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_get_current_graph",
  "Get the graph data from the currently open graph editor panel in VS Code. Returns the VP2GraphData with nodes, connections, automation name, and description.",
  {},
  async () => {
    const result = await bridgeGet("/graph-state");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_update_graph",
  "Update the graph in the currently open graph editor with new VP2GraphData. The graphData must include 'nodes' (array) and 'connections' (array). Changes appear immediately in the editor as unsaved.",
  {
    graphData: z.any().describe("VP2GraphData JSON object with nodes and connections arrays"),
  },
  async ({ graphData }) => {
    const result = await bridgePost("/graph-load", { graphData });
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_get_current_wiki",
  "Get the wiki page currently open in the VS Code wiki editor panel. Returns the page title, slug, and content.",
  {},
  async () => {
    const result = await bridgeGet("/wiki-state");
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_search_wiki",
  "Search wiki pages by query string",
  {
    query: z.string().describe("Search query"),
  },
  async ({ query }) => {
    const result = await bridgeGet(`/api/wiki/search?q=${encodeURIComponent(query)}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_get_wiki_page",
  "Get the full content of a wiki page by slug",
  {
    slug: z.string().describe("Wiki page slug"),
  },
  async ({ slug }) => {
    const result = await bridgeGet(`/api/wiki/by-slug/${slug}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_create_wiki_page",
  "Create a new wiki page in SOAS. Use parent_id to nest under an existing page.",
  {
    title: z.string().describe("Page title"),
    slug: z.string().optional().describe("URL slug (auto-generated from title if omitted)"),
    content: z.string().optional().describe("Page content (HTML or markdown)"),
    parent_id: z.string().optional().describe("Parent wiki page UUID to nest this page under"),
    tags: z.array(z.string()).optional().describe("Tags for the page"),
    icon: z.string().optional().describe("Icon identifier for the page"),
  },
  async ({ title, slug, content, parent_id, tags, icon }) => {
    const body = { title, content: content || "" };
    if (slug) body.slug = slug;
    if (parent_id) body.parent_id = parent_id;
    if (tags) body.tags = tags;
    if (icon) body.icon = icon;
    const result = await bridgePost("/api/wiki", body);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_update_wiki_page",
  "Update an existing wiki page's title or content",
  {
    pageId: z.string().describe("The wiki page UUID"),
    title: z.string().optional().describe("New page title"),
    content: z.string().optional().describe("New page content"),
  },
  async ({ pageId, title, content }) => {
    const body = {};
    if (title !== undefined) body.title = title;
    if (content !== undefined) body.content = content;
    const result = await bridgePatch(`/api/wiki/${pageId}`, body);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_delete_wiki_page",
  "Delete a wiki page by its UUID",
  {
    pageId: z.string().describe("The wiki page UUID to delete"),
  },
  async ({ pageId }) => {
    const result = await bridgeDelete(`/api/wiki/${pageId}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_list_wiki_pages",
  "List all wiki pages in SOAS",
  {
    page: z.number().default(1),
  },
  async ({ page }) => {
    const result = await bridgeGet(`/api/wiki?per_page=50&page=${page}`);
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_run_automation",
  "Execute an automation and get the execution ID",
  {
    automationId: z.string().describe("The automation UUID to execute"),
    parameters: z.record(z.any()).optional().describe("Optional parameters to pass to the automation"),
  },
  async ({ automationId, parameters }) => {
    const result = await bridgePost(`/api/automations/${automationId}/execute`, {
      parameters: parameters || {},
    });
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

server.tool(
  "soas_create_incident",
  "Create a new incident in the SOC platform",
  {
    title: z.string().describe("Incident title"),
    severity: z.enum(["critical", "high", "medium", "low", "informational"]),
    summary: z.string().optional().describe("Brief summary of the incident"),
  },
  async ({ title, severity, summary }) => {
    const result = await bridgePost("/api/incidents", { title, severity, summary });
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  }
);

// --- Start ---

const transport = new StdioServerTransport();
await server.connect(transport);
