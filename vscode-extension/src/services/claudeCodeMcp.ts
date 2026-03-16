/**
 * Auto-configures Claude Code's MCP server entry so users don't need to manually run `claude mcp add`.
 * Writes a user-scoped MCP server entry to ~/.claude.json on extension activation.
 * Idempotent — skips if already configured.
 */

import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { log } from "../utils/notifications";

const BRIDGE_PORT = 19542;

export async function ensureClaudeCodeMcpConfig(context: vscode.ExtensionContext): Promise<void> {
  const homedir = process.env.HOME || process.env.USERPROFILE;
  if (!homedir) return;

  const claudeJsonPath = path.join(homedir, ".claude.json");

  // Find the MCP server script bundled with the extension
  const mcpServerPath = path.join(context.extensionPath, "mcp-server", "index.mjs")
    .replace(/\\/g, "/"); // Normalize to forward slashes for cross-platform

  // Verify the MCP server script exists
  if (!fs.existsSync(mcpServerPath)) {
    log("MCP server script not found, skipping auto-config");
    return;
  }

  let config: Record<string, unknown> = {};

  // Read existing config
  if (fs.existsSync(claudeJsonPath)) {
    try {
      const raw = fs.readFileSync(claudeJsonPath, "utf-8");
      config = JSON.parse(raw);
    } catch {
      log("Could not parse ~/.claude.json, skipping MCP auto-config");
      return;
    }
  }

  // Check if soas MCP server is already configured at user scope
  const mcpServers = (config.mcpServers || {}) as Record<string, unknown>;
  const existing = mcpServers.soas as Record<string, unknown> | undefined;

  if (existing) {
    // Update the path if it changed (e.g., extension updated)
    const existingArgs = (existing.args || []) as string[];
    if (existingArgs[0] === mcpServerPath) {
      return; // Already configured with correct path
    }
    log("Updating SOAS MCP server path in Claude Code config");
  } else {
    log("Registering SOAS MCP server in Claude Code config");
  }

  // Write/update the MCP server entry
  mcpServers.soas = {
    type: "stdio",
    command: "node",
    args: [mcpServerPath],
    env: {
      SOAS_BRIDGE_URL: `http://127.0.0.1:${BRIDGE_PORT}`,
    },
  };
  config.mcpServers = mcpServers;

  fs.writeFileSync(claudeJsonPath, JSON.stringify(config, null, 2), "utf-8");
  log("SOAS MCP server registered in Claude Code (~/.claude.json)");
}
