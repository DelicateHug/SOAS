/**
 * TreeDataProvider for the admin section.
 * Shows a static list of admin pages that open webview panels.
 */

import * as vscode from "vscode";
import type { AuthManager } from "../auth/authManager";

interface AdminItem {
  label: string;
  icon: string;
  command: string;
  description?: string;
}

const ADMIN_ITEMS: AdminItem[] = [
  { label: "Users", icon: "people", command: "soas.admin.users", description: "Manage users and roles" },
  { label: "Roles & Permissions", icon: "shield", command: "soas.admin.roles", description: "Define roles and permissions" },
  { label: "SOAS Variables", icon: "symbol-variable", command: "soas.admin.soasVariables", description: "System-wide variables" },
  { label: "Incident Variables", icon: "file-text", command: "soas.admin.incidentVariables", description: "Incident metadata schema" },
  { label: "Form Definitions", icon: "clippy", command: "soas.admin.formDefinitions", description: "Dynamic form templates" },
  { label: "Webhooks", icon: "radio-tower", command: "soas.admin.webhooks", description: "Webhook ingest config" },
  { label: "Webhook Sources", icon: "plug", command: "soas.admin.webhookSources", description: "External source types" },
  { label: "Normalization", icon: "settings", command: "soas.admin.normalization", description: "Field mapping rules" },
  { label: "User Secrets", icon: "key", command: "soas.admin.userSecrets", description: "Manage user secrets" },
  { label: "Review Changes", icon: "git-pull-request", command: "soas.admin.reviewChanges", description: "Change request approvals" },
  { label: "Settings", icon: "gear", command: "soas.admin.settings", description: "System configuration" },
];

export class AdminTreeProvider implements vscode.TreeDataProvider<AdminItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<AdminItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly authManager: AuthManager) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: AdminItem): vscode.TreeItem {
    const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None);
    item.description = element.description;
    item.iconPath = new vscode.ThemeIcon(element.icon);
    item.command = {
      command: element.command,
      title: element.label,
    };
    item.contextValue = "admin-item";
    return item;
  }

  async getChildren(): Promise<AdminItem[]> {
    if (!this.authManager.isAuthenticated) return [];
    return ADMIN_ITEMS;
  }
}
