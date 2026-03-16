/**
 * Command handlers for AI-assisted features.
 */

import * as vscode from "vscode";
import type { AuthManager } from "../auth/authManager";

export function registerAiCommands(
  context: vscode.ExtensionContext,
  _authManager: AuthManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.ai.explainAutomation", async () => {
      // Open chat with pre-filled prompt
      await vscode.commands.executeCommand("workbench.action.chat.open", {
        query: "@soas Explain the currently open automation — what does it do step by step?",
      });
    }),

    vscode.commands.registerCommand("soas.ai.generateAutomation", async () => {
      const description = await vscode.window.showInputBox({
        prompt: "Describe the automation you want to create",
        placeHolder: "e.g., Check VirusTotal for each IOC in an incident and update severity if malicious",
      });
      if (!description) return;

      await vscode.commands.executeCommand("workbench.action.chat.open", {
        query: `@soas Generate an automation: ${description}`,
      });
    }),

    vscode.commands.registerCommand("soas.ai.generateWikiPage", async () => {
      const description = await vscode.window.showInputBox({
        prompt: "What should the wiki page be about?",
        placeHolder: "e.g., Document the VirusTotal Check automation",
      });
      if (!description) return;

      await vscode.commands.executeCommand("workbench.action.chat.open", {
        query: `@soas Generate a wiki page: ${description}`,
      });
    }),

    vscode.commands.registerCommand("soas.ai.improveWikiPage", async () => {
      await vscode.commands.executeCommand("workbench.action.chat.open", {
        query: "@soas Review and improve the currently open wiki page. Suggest better structure, more detail, and clearer writing.",
      });
    })
  );
}
