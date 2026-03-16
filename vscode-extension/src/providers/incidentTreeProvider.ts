/**
 * TreeDataProvider for incidents, grouped by status.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { logError } from "../utils/notifications";

interface IncidentListItem {
  id: string;
  title: string;
  severity: string;
  status: string;
  created_at: string;
  assigned_count: number;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number; page: number; per_page: number; total_pages: number };
}

const SEVERITY_ICONS: Record<string, string> = {
  critical: "$(error)",
  high: "$(warning)",
  medium: "$(info)",
  low: "$(circle-outline)",
  informational: "$(note)",
};

const STATUS_ORDER = [
  "detected",
  "triaging",
  "investigating",
  "containing",
  "remediating",
  "resolved",
  "closed",
  "false_positive",
];

type TreeItemData =
  | { kind: "status-group"; status: string; count: number }
  | { kind: "incident"; incident: IncidentListItem };

export class IncidentTreeProvider implements vscode.TreeDataProvider<TreeItemData> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<TreeItemData | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private incidents: IncidentListItem[] = [];
  private filterSeverity: string | undefined;
  private filterStatus: string | undefined;

  constructor(
    private readonly authManager: AuthManager,
    private readonly statusBar: StatusBarManager
  ) {}

  refresh(): void {
    this._onDidChangeTreeData.fire(undefined);
  }

  setFilter(severity?: string, status?: string): void {
    this.filterSeverity = severity;
    this.filterStatus = status;
    this.refresh();
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

    const inc = element.incident;
    const severityIcon = SEVERITY_ICONS[inc.severity] || "$(circle)";
    const item = new vscode.TreeItem(inc.title, vscode.TreeItemCollapsibleState.None);
    item.description = `${severityIcon} ${inc.severity}`;
    item.tooltip = `${inc.title}\nSeverity: ${inc.severity}\nStatus: ${inc.status}\nCreated: ${new Date(inc.created_at).toLocaleString()}`;
    item.contextValue = `incident-${inc.status}`;
    item.iconPath = this.getSeverityIcon(inc.severity);
    item.command = {
      command: "soas.incidents.open",
      title: "Open Incident",
      arguments: [inc],
    };
    return item;
  }

  async getChildren(element?: TreeItemData): Promise<TreeItemData[]> {
    if (!this.authManager.isAuthenticated) return [];

    if (!element) {
      // Root level: fetch incidents and group by status
      try {
        const teamId = this.statusBar.getActiveTeamId();
        if (!teamId) return [];
        let url = `/incidents?per_page=100&team_id=${teamId}`;
        if (this.filterSeverity) url += `&severity=${this.filterSeverity}`;
        if (this.filterStatus) url += `&status=${this.filterStatus}`;

        const result = await apiClient.get<PaginatedResponse<IncidentListItem>>(url);
        this.incidents = result.data;

        // Group by status
        const groups = new Map<string, number>();
        for (const inc of this.incidents) {
          groups.set(inc.status, (groups.get(inc.status) || 0) + 1);
        }

        return STATUS_ORDER
          .filter((s) => groups.has(s))
          .map((status) => ({
            kind: "status-group" as const,
            status,
            count: groups.get(status)!,
          }));
      } catch (err) {
        logError("Failed to fetch incidents", err);
        return [];
      }
    }

    if (element.kind === "status-group") {
      return this.incidents
        .filter((inc) => inc.status === element.status)
        .map((incident) => ({ kind: "incident" as const, incident }));
    }

    return [];
  }

  private getSeverityIcon(severity: string): vscode.ThemeIcon {
    switch (severity) {
      case "critical":
        return new vscode.ThemeIcon("error", new vscode.ThemeColor("charts.red"));
      case "high":
        return new vscode.ThemeIcon("warning", new vscode.ThemeColor("charts.orange"));
      case "medium":
        return new vscode.ThemeIcon("info", new vscode.ThemeColor("charts.yellow"));
      case "low":
        return new vscode.ThemeIcon("circle-outline", new vscode.ThemeColor("charts.blue"));
      default:
        return new vscode.ThemeIcon("note");
    }
  }
}
