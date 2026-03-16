/**
 * Command handlers for issue operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { IssueTreeProvider } from "../providers/issueTreeProvider";
import { showError, showInfo, logError } from "../utils/notifications";

const ISSUE_STATUSES = ["open", "in_progress", "resolved", "closed"];

export function registerIssueCommands(
  context: vscode.ExtensionContext,
  tree: IssueTreeProvider,
  authManager: AuthManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.issues.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.issues.create", async () => {
      const title = await vscode.window.showInputBox({
        prompt: "Issue title",
        placeHolder: "e.g., False positive alerts from firewall",
      });
      if (!title) return;

      const description = await vscode.window.showInputBox({
        prompt: "Issue description (optional)",
        placeHolder: "Brief description of the issue",
      });

      try {
        await apiClient.post("/issues", {
          title,
          description: description || undefined,
        });
        showInfo(`Issue "${title}" created`);
        tree.refresh();
      } catch (err) {
        logError("Failed to create issue", err);
        showError("Failed to create issue");
      }
    }),

    vscode.commands.registerCommand("soas.issues.open", (issue: { id: string }) => {
      // For now, show a quick info — can be expanded to a webview panel
      vscode.window.showInformationMessage(`Issue: ${issue.id}`);
    }),

    vscode.commands.registerCommand("soas.issues.changeStatus", async (element: { id?: string }) => {
      if (!element?.id) return;

      const status = await vscode.window.showQuickPick(ISSUE_STATUSES, {
        placeHolder: "Select new status",
      });
      if (!status) return;

      try {
        await apiClient.patch(`/issues/${element.id}`, { status });
        showInfo(`Issue status changed to ${status}`);
        tree.refresh();
      } catch (err) {
        logError("Failed to change issue status", err);
        showError("Failed to change issue status");
      }
    })
  );
}
