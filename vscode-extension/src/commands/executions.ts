/**
 * Command handlers for execution operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { ExecutionTreeProvider } from "../providers/executionTreeProvider";
import { BasePanel } from "../panels/basePanel";
import { showError, showInfo, logError } from "../utils/notifications";

export function registerExecutionCommands(
  context: vscode.ExtensionContext,
  tree: ExecutionTreeProvider,
  authManager: AuthManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.executions.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.executions.view", (execution: { id: string; automation_name?: string }) => {
      BasePanel.createOrShow(
        context.extensionUri,
        "executionOutput",
        `Execution: ${execution.automation_name || execution.id}`,
        authManager,
        { executionId: execution.id }
      );
    }),

    vscode.commands.registerCommand("soas.executions.cancel", async (element: { id?: string; status?: string }) => {
      if (!element?.id) return;

      const confirm = await vscode.window.showWarningMessage(
        "Cancel this execution?",
        { modal: true },
        "Cancel Execution"
      );
      if (confirm !== "Cancel Execution") return;

      try {
        await apiClient.post(`/executions/${element.id}/cancel`);
        showInfo("Execution cancelled");
        tree.refresh();
      } catch (err) {
        logError("Failed to cancel execution", err);
        showError("Failed to cancel execution");
      }
    })
  );
}
