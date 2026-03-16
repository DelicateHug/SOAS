/**
 * TreeDataProvider for issues, grouped by status.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import { logError } from "../utils/notifications";

interface IssueItem {
  id: string;
  title: string;
  status: string;
  assigned_to: { id: string; username: string; display_name: string } | null;
  link_count: number;
  note_count: number;
  created_at: string;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number };
}

const STATUS_ORDER = ["open", "in_progress", "resolved", "closed", "wont_fix"];

type TreeItemData =
  | { kind: "status-group"; status: string; count: number }
  | { kind: "issue"; issue: IssueItem };

export class IssueTreeProvider implements vscode.TreeDataProvider<TreeItemData> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<TreeItemData | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private issues: IssueItem[] = [];

  constructor(private readonly authManager: AuthManager) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: TreeItemData): vscode.TreeItem {
    if (element.kind === "status-group") {
      const item = new vscode.TreeItem(
        `${element.status.replace("_", " ")} (${element.count})`,
        vscode.TreeItemCollapsibleState.Expanded
      );
      item.contextValue = "status-group";
      item.iconPath = new vscode.ThemeIcon("folder");
      return item;
    }

    const issue = element.issue;
    const item = new vscode.TreeItem(issue.title, vscode.TreeItemCollapsibleState.None);
    item.description = issue.assigned_to?.display_name;
    item.tooltip = `${issue.title}\nStatus: ${issue.status}\nAssigned: ${issue.assigned_to?.display_name || "Unassigned"}\nLinks: ${issue.link_count}\nNotes: ${issue.note_count}`;
    item.contextValue = `issue-${issue.status}`;
    item.iconPath = this.getStatusIcon(issue.status);
    item.command = {
      command: "soas.issues.open",
      title: "Open Issue",
      arguments: [issue],
    };
    return item;
  }

  async getChildren(element?: TreeItemData): Promise<TreeItemData[]> {
    if (!this.authManager.isAuthenticated) return [];

    if (!element) {
      try {
        const result = await apiClient.get<PaginatedResponse<IssueItem>>(
          "/issues?per_page=100"
        );
        this.issues = result.data;

        const groups = new Map<string, number>();
        for (const i of this.issues) {
          groups.set(i.status, (groups.get(i.status) || 0) + 1);
        }

        return STATUS_ORDER
          .filter((s) => groups.has(s))
          .map((status) => ({
            kind: "status-group" as const,
            status,
            count: groups.get(status)!,
          }));
      } catch (err) {
        logError("Failed to fetch issues", err);
        return [];
      }
    }

    if (element.kind === "status-group") {
      return this.issues
        .filter((i) => i.status === element.status)
        .map((issue) => ({ kind: "issue" as const, issue }));
    }

    return [];
  }

  private getStatusIcon(status: string): vscode.ThemeIcon {
    switch (status) {
      case "open":
        return new vscode.ThemeIcon("circle-large-outline", new vscode.ThemeColor("charts.blue"));
      case "in_progress":
        return new vscode.ThemeIcon("circle-large-filled", new vscode.ThemeColor("charts.yellow"));
      case "resolved":
        return new vscode.ThemeIcon("check", new vscode.ThemeColor("charts.green"));
      case "closed":
        return new vscode.ThemeIcon("circle-slash", new vscode.ThemeColor("charts.purple"));
      case "wont_fix":
        return new vscode.ThemeIcon("close", new vscode.ThemeColor("charts.red"));
      default:
        return new vscode.ThemeIcon("circle");
    }
  }
}
