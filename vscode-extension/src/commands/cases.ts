/**
 * Command handlers for case operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { CaseTreeProvider } from "../providers/caseTreeProvider";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { BasePanel } from "../panels/basePanel";
import { showError, showInfo, logError } from "../utils/notifications";

const PRIORITIES = ["critical", "high", "medium", "low"];

export function registerCaseCommands(
  context: vscode.ExtensionContext,
  tree: CaseTreeProvider,
  authManager: AuthManager,
  statusBar: StatusBarManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.cases.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.cases.create", async () => {
      const title = await vscode.window.showInputBox({
        prompt: "Case title",
        placeHolder: "e.g., Phishing Campaign Investigation",
      });
      if (!title) return;

      const priority = await vscode.window.showQuickPick(PRIORITIES, {
        placeHolder: "Select priority",
      });
      if (!priority) return;

      try {
        const teamId = statusBar.getActiveTeamId();
        await apiClient.post("/cases", {
          title,
          priority,
          team_id: teamId || undefined,
        });
        showInfo(`Case "${title}" created`);
        tree.refresh();
      } catch (err) {
        logError("Failed to create case", err);
        showError("Failed to create case");
      }
    }),

    vscode.commands.registerCommand("soas.cases.open", (caseItem: { id: string }) => {
      BasePanel.createOrShow(
        context.extensionUri,
        "caseDetail",
        "Case",
        authManager,
        { caseId: caseItem.id }
      );
    })
  );
}
