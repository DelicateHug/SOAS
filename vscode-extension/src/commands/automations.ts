/**
 * Command handlers for automation operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { AutomationTreeProvider } from "../providers/automationTreeProvider";
import { BasePanel } from "../panels/basePanel";
import { showError, showInfo, logError } from "../utils/notifications";

export function registerAutomationCommands(
  context: vscode.ExtensionContext,
  tree: AutomationTreeProvider,
  authManager: AuthManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.automations.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.automations.create", async () => {
      const name = await vscode.window.showInputBox({
        prompt: "Automation name",
        placeHolder: "e.g., Check VirusTotal IOCs",
      });
      if (!name) return;

      try {
        const result = await apiClient.post<{ id: string }>("/automations", { name });
        showInfo(`Automation "${name}" created`);
        tree.refresh();
        // Open in graph editor
        BasePanel.createOrShow(
          context.extensionUri,
          "graphEditor",
          name,
          authManager,
          { automationId: result.id }
        );
      } catch (err) {
        logError("Failed to create automation", err);
        showError("Failed to create automation");
      }
    }),

    vscode.commands.registerCommand("soas.automations.openEditor", (automation: { id: string; name: string }) => {
      BasePanel.createOrShow(
        context.extensionUri,
        "graphEditor",
        automation.name || "Graph Editor",
        authManager,
        { automationId: automation.id }
      );
    }),

    vscode.commands.registerCommand("soas.automations.compile", async (element: { kind: string; automation?: { id: string; name: string } }) => {
      const automation = element?.kind === "automation" ? element.automation : undefined;
      if (!automation) return;

      try {
        await vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: `Compiling ${automation.name}...` },
          async () => {
            await apiClient.post(`/automations/${automation.id}/versions`);
          }
        );
        showInfo(`${automation.name} compiled successfully`);
        tree.refresh();
      } catch (err) {
        logError("Compilation failed", err);
        showError("Compilation failed");
      }
    }),

    vscode.commands.registerCommand("soas.automations.run", async (element: { kind: string; automation?: { id: string; name: string } }) => {
      const automation = element?.kind === "automation" ? element.automation : undefined;
      if (!automation) return;

      try {
        const result = await apiClient.post<{ execution_id: string }>(
          `/automations/${automation.id}/execute`
        );
        showInfo(`${automation.name} started (execution: ${result.execution_id})`);
        // Open execution output panel
        BasePanel.createOrShow(
          context.extensionUri,
          "executionOutput",
          `Execution: ${automation.name}`,
          authManager,
          { executionId: result.execution_id }
        );
      } catch (err) {
        logError("Failed to run automation", err);
        showError("Failed to run automation");
      }
    }),

    vscode.commands.registerCommand("soas.automations.testRun", async (element: { kind: string; automation?: { id: string; name: string } }) => {
      const automation = element?.kind === "automation" ? element.automation : undefined;
      if (!automation) return;

      try {
        const result = await apiClient.post<{ execution_id: string }>(
          `/automations/${automation.id}/test-run`
        );
        showInfo(`Test run started for ${automation.name}`);
        BasePanel.createOrShow(
          context.extensionUri,
          "executionOutput",
          `Test: ${automation.name}`,
          authManager,
          { executionId: result.execution_id }
        );
      } catch (err) {
        logError("Failed to start test run", err);
        showError("Failed to start test run");
      }
    })
  );
}
