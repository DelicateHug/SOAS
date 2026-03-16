/**
 * TreeDataProvider for automations, grouped by status.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { logError } from "../utils/notifications";

interface AutomationItem {
  id: string;
  name: string;
  description: string;
  status: string;
  version: number;
  tags: string[];
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number };
}

const STATUS_ORDER = ["active", "draft", "disabled", "archived"];

type TreeItemData =
  | { kind: "status-group"; status: string; count: number }
  | { kind: "automation"; automation: AutomationItem };

export class AutomationTreeProvider implements vscode.TreeDataProvider<TreeItemData> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<TreeItemData | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private automations: AutomationItem[] = [];

  constructor(
    private readonly authManager: AuthManager,
    private readonly statusBar: StatusBarManager
  ) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: TreeItemData): vscode.TreeItem {
    if (element.kind === "status-group") {
      const item = new vscode.TreeItem(
        `${element.status} (${element.count})`,
        vscode.TreeItemCollapsibleState.Expanded
      );
      item.contextValue = "status-group";
      item.iconPath = new vscode.ThemeIcon("folder");
      return item;
    }

    const auto = element.automation;
    const item = new vscode.TreeItem(auto.name, vscode.TreeItemCollapsibleState.None);
    item.description = `v${auto.version}`;
    item.tooltip = `${auto.name}\n${auto.description || ""}\nStatus: ${auto.status}\nVersion: ${auto.version}\nTags: ${auto.tags.join(", ") || "none"}`;
    item.contextValue = `automation-${auto.status}`;
    item.iconPath = new vscode.ThemeIcon("zap", this.getStatusColor(auto.status));
    item.command = {
      command: "soas.automations.openEditor",
      title: "Open in Graph Editor",
      arguments: [auto],
    };
    return item;
  }

  async getChildren(element?: TreeItemData): Promise<TreeItemData[]> {
    if (!this.authManager.isAuthenticated) return [];

    if (!element) {
      try {
        const teamId = this.statusBar.getActiveTeamId();
        if (!teamId) return [];
        let url = `/automations?per_page=100&team_id=${teamId}`;

        const result = await apiClient.get<PaginatedResponse<AutomationItem>>(url);
        this.automations = result.data;

        const groups = new Map<string, number>();
        for (const a of this.automations) {
          groups.set(a.status, (groups.get(a.status) || 0) + 1);
        }

        return STATUS_ORDER
          .filter((s) => groups.has(s))
          .map((status) => ({
            kind: "status-group" as const,
            status,
            count: groups.get(status)!,
          }));
      } catch (err) {
        logError("Failed to fetch automations", err);
        return [];
      }
    }

    if (element.kind === "status-group") {
      return this.automations
        .filter((a) => a.status === element.status)
        .map((automation) => ({ kind: "automation" as const, automation }));
    }

    return [];
  }

  private getStatusColor(status: string): vscode.ThemeColor | undefined {
    switch (status) {
      case "active":
        return new vscode.ThemeColor("charts.green");
      case "draft":
        return new vscode.ThemeColor("charts.yellow");
      case "disabled":
        return new vscode.ThemeColor("charts.red");
      default:
        return undefined;
    }
  }
}
