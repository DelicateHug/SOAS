/**
 * TreeDataProvider for cases, grouped by status.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { logError } from "../utils/notifications";

interface CaseItem {
  id: string;
  title: string;
  status: string;
  priority: string;
  incident_count: number;
  created_at: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number };
}

const STATUS_ORDER = ["open", "investigating", "pending", "closed", "archived"];

type TreeItemData =
  | { kind: "status-group"; status: string; count: number }
  | { kind: "case"; caseItem: CaseItem };

export class CaseTreeProvider implements vscode.TreeDataProvider<TreeItemData> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<TreeItemData | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private cases: CaseItem[] = [];

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

    const c = element.caseItem;
    const item = new vscode.TreeItem(c.title, vscode.TreeItemCollapsibleState.None);
    item.description = `${c.incident_count} incidents`;
    item.tooltip = `${c.title}\nStatus: ${c.status}\nPriority: ${c.priority}\nIncidents: ${c.incident_count}`;
    item.contextValue = `case-${c.status}`;
    item.iconPath = new vscode.ThemeIcon("layers");
    item.command = {
      command: "soas.cases.open",
      title: "Open Case",
      arguments: [c],
    };
    return item;
  }

  async getChildren(element?: TreeItemData): Promise<TreeItemData[]> {
    if (!this.authManager.isAuthenticated) return [];

    if (!element) {
      try {
        const teamId = this.statusBar.getActiveTeamId();
        if (!teamId) return [];
        let url = `/cases?per_page=100&team_id=${teamId}`;

        const result = await apiClient.get<PaginatedResponse<CaseItem>>(url);
        this.cases = result.data;

        const groups = new Map<string, number>();
        for (const c of this.cases) {
          groups.set(c.status, (groups.get(c.status) || 0) + 1);
        }

        return STATUS_ORDER
          .filter((s) => groups.has(s))
          .map((status) => ({
            kind: "status-group" as const,
            status,
            count: groups.get(status)!,
          }));
      } catch (err) {
        logError("Failed to fetch cases", err);
        return [];
      }
    }

    if (element.kind === "status-group") {
      return this.cases
        .filter((c) => c.status === element.status)
        .map((caseItem) => ({ kind: "case" as const, caseItem }));
    }

    return [];
  }
}
