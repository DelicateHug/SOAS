/**
 * Command handlers for admin panel operations.
 * Each command opens a webview panel that reuses the corresponding frontend admin page.
 */

import * as vscode from "vscode";
import type { AuthManager } from "../auth/authManager";
import type { AdminTreeProvider } from "../providers/adminTreeProvider";
import { BasePanel } from "../panels/basePanel";

interface AdminPanelConfig {
  command: string;
  panelType: string;
  title: string;
}

const ADMIN_PANELS: AdminPanelConfig[] = [
  { command: "soas.admin.users", panelType: "adminUsers", title: "Users" },
  { command: "soas.admin.roles", panelType: "adminRoles", title: "Roles & Permissions" },
  { command: "soas.admin.soasVariables", panelType: "adminSoasVariables", title: "SOAS Variables" },
  { command: "soas.admin.incidentVariables", panelType: "adminIncidentVariables", title: "Incident Variables" },
  { command: "soas.admin.formDefinitions", panelType: "adminFormDefinitions", title: "Form Definitions" },
  { command: "soas.admin.webhooks", panelType: "adminWebhooks", title: "Webhooks" },
  { command: "soas.admin.webhookSources", panelType: "adminWebhookSources", title: "Webhook Sources" },
  { command: "soas.admin.normalization", panelType: "adminNormalization", title: "Normalization" },
  { command: "soas.admin.userSecrets", panelType: "adminUserSecrets", title: "User Secrets" },
  { command: "soas.admin.reviewChanges", panelType: "adminReviewChanges", title: "Review Changes" },
  { command: "soas.admin.settings", panelType: "adminSettings", title: "Settings" },
];

export function registerAdminCommands(
  context: vscode.ExtensionContext,
  tree: AdminTreeProvider,
  authManager: AuthManager
): void {
  // Register refresh command
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.admin.refresh", () => {
      tree.refresh();
    })
  );

  // Register a command for each admin panel
  for (const config of ADMIN_PANELS) {
    context.subscriptions.push(
      vscode.commands.registerCommand(config.command, () => {
        BasePanel.createOrShow(
          context.extensionUri,
          config.panelType as never,
          config.title,
          authManager,
          { adminPanel: config.panelType }
        );
      })
    );
  }
}
