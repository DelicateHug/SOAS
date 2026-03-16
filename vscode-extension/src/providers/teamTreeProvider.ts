/**
 * TreeDataProvider for teams.
 * Shows the user's teams with members, variables, and allows management actions.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { logError } from "../utils/notifications";

export interface TeamItem {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  is_default: boolean;
  member_count: number;
}

export interface PaginatedTeams {
  data: TeamItem[];
  meta: { total: number };
}

export interface TeamMember {
  user_id: string;
  username: string;
  display_name: string;
  team_role: string;
  roles: { id: string; name: string; display_name: string }[];
}

export interface TeamVariable {
  id: string;
  team_id: string;
  name: string;
  description: string | null;
  value: unknown;
  is_secret: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginatedVariables {
  data: TeamVariable[];
  meta: { total: number };
}

export type TreeItemData =
  | { type: "team"; team: TeamItem }
  | { type: "member-header"; teamId: string }
  | { type: "member"; member: TeamMember; teamId: string }
  | { type: "variable-header"; teamId: string }
  | { type: "variable"; variable: TeamVariable; teamId: string };

export class TeamTreeProvider implements vscode.TreeDataProvider<TreeItemData> {
  private readonly _onDidChangeTreeData = new vscode.EventEmitter<TreeItemData | undefined>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private teams: TeamItem[] = [];

  constructor(
    private readonly authManager: AuthManager,
    private readonly statusBar: StatusBarManager,
  ) {}

  refresh(): void {
    this.teams = [];
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element: TreeItemData): vscode.TreeItem {
    if (element.type === "team") {
      const { team } = element;
      const isActive = team.id === this.statusBar.getActiveTeamId();
      const item = new vscode.TreeItem(
        team.display_name,
        vscode.TreeItemCollapsibleState.Collapsed
      );
      item.description = `${team.member_count} member${team.member_count !== 1 ? "s" : ""}${isActive ? " (active)" : ""}`;
      item.iconPath = new vscode.ThemeIcon(isActive ? "organization" : "people");
      item.tooltip = [
        team.display_name,
        team.description || "",
        `Slug: ${team.name}`,
        `Members: ${team.member_count}`,
        team.is_default ? "(Default team)" : "",
        isActive ? "(Currently active)" : "",
      ].filter(Boolean).join("\n");
      // Encode both active status and default status into contextValue
      if (team.is_default) {
        item.contextValue = isActive ? "team-default-active" : "team-default";
      } else {
        item.contextValue = isActive ? "team-active" : "team";
      }
      return item;
    }

    if (element.type === "member-header") {
      const item = new vscode.TreeItem("Members", vscode.TreeItemCollapsibleState.Expanded);
      item.iconPath = new vscode.ThemeIcon("people");
      item.contextValue = "member-header";
      return item;
    }

    if (element.type === "variable-header") {
      const item = new vscode.TreeItem("Variables", vscode.TreeItemCollapsibleState.Collapsed);
      item.iconPath = new vscode.ThemeIcon("symbol-variable");
      item.contextValue = "variable-header";
      return item;
    }

    if (element.type === "variable") {
      const { variable } = element;
      const item = new vscode.TreeItem(variable.name, vscode.TreeItemCollapsibleState.None);
      if (variable.is_secret) {
        item.description = "***";
        item.iconPath = new vscode.ThemeIcon("key");
      } else {
        const val = typeof variable.value === "string" ? variable.value : JSON.stringify(variable.value);
        item.description = val.length > 40 ? val.slice(0, 40) + "..." : val;
        item.iconPath = new vscode.ThemeIcon("symbol-variable");
      }
      item.tooltip = [
        variable.name,
        variable.description || "",
        variable.is_secret ? "(Secret)" : `Value: ${typeof variable.value === "string" ? variable.value : JSON.stringify(variable.value)}`,
      ].filter(Boolean).join("\n");
      item.contextValue = "team-variable";
      return item;
    }

    // member
    const { member } = element;
    const item = new vscode.TreeItem(member.display_name, vscode.TreeItemCollapsibleState.None);
    const roleNames = member.roles.map((r) => r.display_name).join(", ");
    item.description = `${member.team_role}${roleNames ? ` · ${roleNames}` : ""}`;
    item.iconPath = new vscode.ThemeIcon(member.team_role === "owner" ? "account" : "person");
    item.tooltip = `@${member.username}\nTeam role: ${member.team_role}\nRoles: ${roleNames || "none"}`;
    item.contextValue = "team-member";
    return item;
  }

  async getChildren(element?: TreeItemData): Promise<TreeItemData[]> {
    if (!this.authManager.isAuthenticated) return [];

    if (!element) {
      // Root: fetch teams
      try {
        const result = await apiClient.get<PaginatedTeams>("/teams?per_page=100");
        this.teams = result.data;
        return this.teams.map((team) => ({ type: "team" as const, team }));
      } catch (err) {
        logError("Failed to fetch teams", err);
        return [];
      }
    }

    if (element.type === "team") {
      return [
        { type: "member-header", teamId: element.team.id },
        { type: "variable-header", teamId: element.team.id },
      ];
    }

    if (element.type === "member-header") {
      try {
        const members = await apiClient.get<TeamMember[]>(`/teams/${element.teamId}/members`);
        return members.map((member) => ({
          type: "member" as const,
          member,
          teamId: element.teamId,
        }));
      } catch (err) {
        logError("Failed to fetch team members", err);
        return [];
      }
    }

    if (element.type === "variable-header") {
      try {
        const result = await apiClient.get<PaginatedVariables>(`/teams/${element.teamId}/variables?per_page=100`);
        return result.data.map((variable) => ({
          type: "variable" as const,
          variable,
          teamId: element.teamId,
        }));
      } catch (err) {
        logError("Failed to fetch team variables", err);
        return [];
      }
    }

    return [];
  }
}
