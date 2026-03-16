/**
 * TreeDataProvider for wiki pages, using the hierarchical tree endpoint.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { logError } from "../utils/notifications";

interface WikiTreeNode {
  id: string;
  title: string;
  slug: string;
  icon: string | null;
  status: string;
  children: WikiTreeNode[];
}

export class WikiTreeProvider implements vscode.TreeDataProvider<WikiTreeNode> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<WikiTreeNode | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private tree: WikiTreeNode[] = [];

  constructor(
    private readonly authManager: AuthManager,
    private readonly statusBar: StatusBarManager,
  ) {}

  refresh(): void {
    this.tree = [];
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: WikiTreeNode): vscode.TreeItem {
    const hasChildren = element.children.length > 0;
    const item = new vscode.TreeItem(
      `${element.icon ? element.icon + " " : ""}${element.title}`,
      hasChildren
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None
    );
    item.tooltip = `${element.title}\nSlug: ${element.slug}\nStatus: ${element.status}`;
    item.contextValue = `wiki-page-${element.status}`;
    item.iconPath = hasChildren
      ? new vscode.ThemeIcon("book")
      : new vscode.ThemeIcon("file-text");
    item.command = {
      command: "soas.wiki.openEditor",
      title: "Edit Wiki Page",
      arguments: [element],
    };
    return item;
  }

  async getChildren(element?: WikiTreeNode): Promise<WikiTreeNode[]> {
    if (!this.authManager.isAuthenticated) return [];

    if (!element) {
      // Root level: fetch tree
      if (this.tree.length === 0) {
        const teamId = this.statusBar.getActiveTeamId();
        if (!teamId) return [];
        try {
          this.tree = await apiClient.get<WikiTreeNode[]>(`/wiki/tree?team_id=${teamId}`);
        } catch (err) {
          logError("Failed to fetch wiki tree", err);
          return [];
        }
      }
      return this.tree;
    }

    return element.children;
  }
}
