/**
 * TreeDataProvider for executions (flat, recent first).
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import { logError } from "../utils/notifications";

interface ExecutionItem {
  id: string;
  automation_id: string;
  automation_name?: string;
  status: string;
  triggered_by: string;
  duration_ms: number | null;
  created_at: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number };
}

const STATUS_ICONS: Record<string, vscode.ThemeIcon> = {
  pending: new vscode.ThemeIcon("clock", new vscode.ThemeColor("charts.yellow")),
  queued: new vscode.ThemeIcon("clock", new vscode.ThemeColor("charts.yellow")),
  running: new vscode.ThemeIcon("sync~spin", new vscode.ThemeColor("charts.blue")),
  completed: new vscode.ThemeIcon("check", new vscode.ThemeColor("charts.green")),
  failed: new vscode.ThemeIcon("error", new vscode.ThemeColor("charts.red")),
  cancelled: new vscode.ThemeIcon("circle-slash", new vscode.ThemeColor("charts.orange")),
  timed_out: new vscode.ThemeIcon("watch", new vscode.ThemeColor("charts.red")),
};

export class ExecutionTreeProvider implements vscode.TreeDataProvider<ExecutionItem> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<ExecutionItem | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  constructor(private readonly authManager: AuthManager) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: ExecutionItem): vscode.TreeItem {
    const name = element.automation_name || "Unknown";
    const item = new vscode.TreeItem(name, vscode.TreeItemCollapsibleState.None);

    const duration = element.duration_ms
      ? `${(element.duration_ms / 1000).toFixed(1)}s`
      : "—";
    const time = new Date(element.created_at).toLocaleString();

    item.description = `${element.status} • ${duration}`;
    item.tooltip = `${name}\nStatus: ${element.status}\nTriggered by: ${element.triggered_by}\nDuration: ${duration}\nStarted: ${time}`;
    item.contextValue = `execution-${element.status}`;
    item.iconPath = STATUS_ICONS[element.status] || new vscode.ThemeIcon("circle");
    item.command = {
      command: "soas.executions.view",
      title: "View Execution",
      arguments: [element],
    };
    return item;
  }

  async getChildren(): Promise<ExecutionItem[]> {
    if (!this.authManager.isAuthenticated) return [];

    try {
      const result = await apiClient.get<PaginatedResponse<ExecutionItem>>(
        "/executions?per_page=50"
      );
      return result.data;
    } catch (err) {
      logError("Failed to fetch executions", err);
      return [];
    }
  }
}
