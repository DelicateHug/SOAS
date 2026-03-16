/**
 * Command handlers for team management operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import type {
  TeamTreeProvider,
  TreeItemData,
  TeamItem,
  TeamMember,
  TeamVariable,
  PaginatedVariables,
} from "../providers/teamTreeProvider";
import { showError, showInfo, logError } from "../utils/notifications";

interface Role {
  id: string;
  name: string;
  display_name: string;
}

interface UserListItem {
  id: string;
  username: string;
  display_name: string;
}

interface PaginatedUsers {
  data: UserListItem[];
  meta: { total: number };
}

interface VariablePermission {
  role_id: string;
  role_name?: string;
  can_read: boolean;
  can_write: boolean;
}

export function registerTeamCommands(
  context: vscode.ExtensionContext,
  tree: TeamTreeProvider,
  authManager: AuthManager,
  statusBar: StatusBarManager,
): void {
  context.subscriptions.push(
    // --- Existing commands moved here ---
    vscode.commands.registerCommand("soas.teams.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.teams.setActive", (item: TreeItemData) => {
      if (item?.type === "team" && item.team) {
        statusBar.setActiveTeam(item.team.id, item.team.name);
      }
    }),

    // --- Create Team ---
    vscode.commands.registerCommand("soas.teams.create", async () => {
      const name = await vscode.window.showInputBox({
        prompt: "Team name (URL-safe slug)",
        placeHolder: "e.g., alpha-team",
        validateInput: (value) => {
          if (!value) return "Name is required";
          if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(value) && !/^[a-z0-9]{1,2}$/.test(value)) {
            return "Must be lowercase alphanumeric with hyphens (e.g., my-team)";
          }
          return undefined;
        },
      });
      if (!name) return;

      const displayName = await vscode.window.showInputBox({
        prompt: "Display name",
        placeHolder: "e.g., Alpha Team",
        value: name.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" "),
      });
      if (!displayName) return;

      const description = await vscode.window.showInputBox({
        prompt: "Description (optional)",
        placeHolder: "What is this team for?",
      });

      try {
        await apiClient.post("/teams", {
          name,
          display_name: displayName,
          description: description || undefined,
        });
        showInfo(`Team "${displayName}" created`);
        tree.refresh();
        // Refresh JWT so new team appears in status bar
        await authManager.refreshSession();
      } catch (err) {
        logError("Failed to create team", err);
        showError("Failed to create team");
      }
    }),

    // --- Edit Team ---
    vscode.commands.registerCommand("soas.teams.edit", async (item: TreeItemData) => {
      const team = extractTeam(item);
      if (!team) return;

      const displayName = await vscode.window.showInputBox({
        prompt: "Display name",
        value: team.display_name,
      });
      if (displayName === undefined) return;

      const description = await vscode.window.showInputBox({
        prompt: "Description",
        value: team.description || "",
      });
      if (description === undefined) return;

      try {
        await apiClient.patch(`/teams/${team.id}`, {
          display_name: displayName,
          description: description || null,
        });
        showInfo(`Team "${displayName}" updated`);
        tree.refresh();
      } catch (err) {
        logError("Failed to update team", err);
        showError("Failed to update team");
      }
    }),

    // --- Delete Team ---
    vscode.commands.registerCommand("soas.teams.delete", async (item: TreeItemData) => {
      const team = extractTeam(item);
      if (!team) return;

      if (team.is_default) {
        showError("Cannot delete the default team");
        return;
      }

      const confirm = await vscode.window.showWarningMessage(
        `Delete team "${team.display_name}"? Resources will become unscoped.`,
        { modal: true },
        "Delete"
      );
      if (confirm !== "Delete") return;

      try {
        await apiClient.delete(`/teams/${team.id}`);
        showInfo(`Team "${team.display_name}" deleted`);
        // If deleted team was active, auto-select another
        if (team.id === statusBar.getActiveTeamId()) {
          await statusBar.autoSelectDefaultTeam();
        }
        tree.refresh();
      } catch (err) {
        logError("Failed to delete team", err);
        showError("Failed to delete team");
      }
    }),

    // --- Add Member ---
    vscode.commands.registerCommand("soas.teams.addMember", async (item: TreeItemData) => {
      const teamId = extractTeamId(item);
      if (!teamId) return;

      // Fetch users and current members in parallel
      let allUsers: UserListItem[];
      let currentMembers: TeamMember[];
      let roles: Role[];
      try {
        const [usersRes, membersRes, rolesRes] = await Promise.all([
          apiClient.get<PaginatedUsers>("/admin/users?per_page=100"),
          apiClient.get<TeamMember[]>(`/teams/${teamId}/members`),
          apiClient.get<Role[]>("/roles"),
        ]);
        allUsers = usersRes.data;
        currentMembers = membersRes;
        roles = rolesRes;
      } catch (err: unknown) {
        logError("Failed to fetch data for add member", err);
        const detail = (err as { detail?: string })?.detail || (err as { error?: string })?.error || "";
        showError(`Failed to load users or roles${detail ? `: ${detail}` : ". You may need admin permissions."}`);
        return;
      }

      const existingIds = new Set(currentMembers.map((m) => m.user_id));
      const availableUsers = allUsers.filter((u) => !existingIds.has(u.id));

      if (availableUsers.length === 0) {
        showInfo("All users are already members of this team.");
        return;
      }

      // Pick user
      const userPick = await vscode.window.showQuickPick(
        availableUsers.map((u) => ({
          label: u.display_name,
          description: `@${u.username}`,
          detail: u.id,
        })),
        { placeHolder: "Select a user to add", title: "Add Team Member" }
      );
      if (!userPick) return;

      // Pick permission roles
      const roleItems: (vscode.QuickPickItem & { roleId: string })[] = roles.map((r) => ({
        label: r.display_name,
        description: r.name,
        roleId: r.id,
        picked: false,
      }));
      const selectedRoles = await vscode.window.showQuickPick(roleItems, {
        placeHolder: "Select permission roles (at least one)",
        title: "Permission Roles",
        canPickMany: true,
      });
      if (!selectedRoles || selectedRoles.length === 0) {
        showError("At least one permission role is required.");
        return;
      }

      // Pick team role
      const teamRole = await vscode.window.showQuickPick(["member", "owner"], {
        placeHolder: "Select team role",
        title: "Team Role",
      });
      if (!teamRole) return;

      try {
        await apiClient.post(`/teams/${teamId}/members`, {
          user_id: userPick.detail,
          role_ids: selectedRoles.map((r) => r.roleId),
          team_role: teamRole,
        });
        showInfo(`Added ${userPick.label} to team`);
        tree.refresh();
      } catch (err) {
        logError("Failed to add member", err);
        showError("Failed to add member");
      }
    }),

    // --- Remove Member ---
    vscode.commands.registerCommand("soas.teams.removeMember", async (item: TreeItemData) => {
      if (item?.type !== "member") return;
      const { member, teamId } = item;

      const confirm = await vscode.window.showWarningMessage(
        `Remove ${member.display_name} (@${member.username}) from this team?`,
        { modal: true },
        "Remove"
      );
      if (confirm !== "Remove") return;

      try {
        await apiClient.delete(`/teams/${teamId}/members/${member.user_id}`);
        showInfo(`Removed ${member.display_name} from team`);
        tree.refresh();
      } catch (err) {
        logError("Failed to remove member", err);
        showError("Failed to remove member");
      }
    }),

    // --- Edit Member ---
    vscode.commands.registerCommand("soas.teams.editMember", async (item: TreeItemData) => {
      if (item?.type !== "member") return;
      const { member, teamId } = item;

      let roles: Role[];
      try {
        roles = await apiClient.get<Role[]>("/roles");
      } catch (err) {
        logError("Failed to fetch roles", err);
        showError("Failed to load roles");
        return;
      }

      const currentRoleIds = new Set(member.roles.map((r) => r.id));
      const roleItems: (vscode.QuickPickItem & { roleId: string })[] = roles.map((r) => ({
        label: r.display_name,
        description: r.name,
        roleId: r.id,
        picked: currentRoleIds.has(r.id),
      }));
      const selectedRoles = await vscode.window.showQuickPick(roleItems, {
        placeHolder: "Select permission roles",
        title: `Edit Roles for ${member.display_name}`,
        canPickMany: true,
      });
      if (!selectedRoles) return;

      const teamRole = await vscode.window.showQuickPick(
        ["member", "owner"].map((r) => ({
          label: r,
          description: r === member.team_role ? "(current)" : undefined,
        })),
        { placeHolder: "Select team role", title: "Team Role" }
      );
      if (!teamRole) return;

      try {
        await apiClient.patch(`/teams/${teamId}/members/${member.user_id}`, {
          role_ids: selectedRoles.map((r) => r.roleId),
          team_role: teamRole.label,
        });
        showInfo(`Updated ${member.display_name}`);
        tree.refresh();
      } catch (err) {
        logError("Failed to update member", err);
        showError("Failed to update member");
      }
    }),

    // --- Create Variable ---
    vscode.commands.registerCommand("soas.teams.createVariable", async (item: TreeItemData) => {
      const teamId = extractTeamId(item);
      if (!teamId) return;

      const name = await vscode.window.showInputBox({
        prompt: "Variable name",
        placeHolder: "e.g., API_KEY",
        validateInput: (v) => v?.trim() ? undefined : "Name is required",
      });
      if (!name) return;

      const value = await vscode.window.showInputBox({
        prompt: "Value (string or JSON)",
        placeHolder: "Enter value...",
      });
      if (value === undefined) return;

      const description = await vscode.window.showInputBox({
        prompt: "Description (optional)",
        placeHolder: "What is this variable for?",
      });

      const secretPick = await vscode.window.showQuickPick(
        [
          { label: "No", description: "Value visible in UI", isSecret: false },
          { label: "Yes", description: "Value masked in UI", isSecret: true },
        ],
        { placeHolder: "Is this a secret?", title: "Secret Variable?" }
      );
      if (!secretPick) return;

      let parsedValue: unknown = value;
      try { parsedValue = JSON.parse(value); } catch { /* keep as string */ }

      try {
        await apiClient.post(`/teams/${teamId}/variables`, {
          name,
          value: parsedValue,
          description: description || null,
          is_secret: secretPick.isSecret,
        });
        showInfo(`Variable "${name}" created`);
        tree.refresh();
      } catch (err) {
        logError("Failed to create variable", err);
        showError("Failed to create variable");
      }
    }),

    // --- Edit Variable ---
    vscode.commands.registerCommand("soas.teams.editVariable", async (item: TreeItemData) => {
      if (item?.type !== "variable") return;
      const { variable, teamId } = item;

      const value = await vscode.window.showInputBox({
        prompt: `Value for ${variable.name}`,
        placeHolder: "Enter new value...",
        value: variable.is_secret ? "" : (typeof variable.value === "string" ? variable.value : JSON.stringify(variable.value ?? "")),
      });
      if (value === undefined) return;

      const description = await vscode.window.showInputBox({
        prompt: "Description",
        value: variable.description || "",
      });
      if (description === undefined) return;

      const secretPick = await vscode.window.showQuickPick(
        [
          { label: "No", description: "Value visible in UI", isSecret: false },
          { label: "Yes", description: "Value masked in UI", isSecret: true },
        ].map((s) => ({
          ...s,
          description: s.isSecret === variable.is_secret ? `${s.description} (current)` : s.description,
        })),
        { placeHolder: "Is this a secret?", title: "Secret Variable?" }
      );
      if (!secretPick) return;

      let parsedValue: unknown = value;
      try { parsedValue = JSON.parse(value); } catch { /* keep as string */ }

      try {
        await apiClient.patch(`/teams/${teamId}/variables/${variable.id}`, {
          value: parsedValue,
          description: description || null,
          is_secret: (secretPick as { isSecret: boolean }).isSecret,
        });
        showInfo(`Variable "${variable.name}" updated`);
        tree.refresh();
      } catch (err) {
        logError("Failed to update variable", err);
        showError("Failed to update variable");
      }
    }),

    // --- Delete Variable ---
    vscode.commands.registerCommand("soas.teams.deleteVariable", async (item: TreeItemData) => {
      if (item?.type !== "variable") return;
      const { variable, teamId } = item;

      const confirm = await vscode.window.showWarningMessage(
        `Delete variable "${variable.name}"?`,
        { modal: true },
        "Delete"
      );
      if (confirm !== "Delete") return;

      try {
        await apiClient.delete(`/teams/${teamId}/variables/${variable.id}`);
        showInfo(`Variable "${variable.name}" deleted`);
        tree.refresh();
      } catch (err) {
        logError("Failed to delete variable", err);
        showError("Failed to delete variable");
      }
    }),

    // --- Manage Variable Permissions ---
    vscode.commands.registerCommand("soas.teams.manageVariablePermissions", async (item: TreeItemData) => {
      if (item?.type !== "variable") return;
      const { variable, teamId } = item;

      let currentPerms: VariablePermission[];
      let roles: Role[];
      try {
        const [permsRes, rolesRes] = await Promise.all([
          apiClient.get<VariablePermission[]>(`/teams/${teamId}/variables/${variable.id}/permissions`),
          apiClient.get<Role[]>("/roles"),
        ]);
        currentPerms = permsRes;
        roles = rolesRes;
      } catch (err) {
        logError("Failed to fetch permissions", err);
        showError("Failed to load permissions or roles");
        return;
      }

      const permMap = new Map(currentPerms.map((p) => [p.role_id, p]));

      // Step 1: Select roles with READ access
      const readItems: (vscode.QuickPickItem & { roleId: string })[] = roles.map((r) => ({
        label: r.display_name,
        description: r.name,
        roleId: r.id,
        picked: permMap.get(r.id)?.can_read ?? false,
      }));
      const readRoles = await vscode.window.showQuickPick(readItems, {
        placeHolder: "Select roles that can READ this variable",
        title: `Read Permissions: ${variable.name}`,
        canPickMany: true,
      });
      if (!readRoles) return;

      const readRoleIds = new Set(readRoles.map((r) => r.roleId));

      // Step 2: From read roles, select which also have WRITE access
      let writeRoleIds = new Set<string>();
      if (readRoles.length > 0) {
        const writeItems: (vscode.QuickPickItem & { roleId: string })[] = readRoles.map((r) => ({
          label: r.label,
          description: r.description,
          roleId: r.roleId,
          picked: permMap.get(r.roleId)?.can_write ?? false,
        }));
        const writeRoles = await vscode.window.showQuickPick(writeItems, {
          placeHolder: "Select roles that can also WRITE this variable",
          title: `Write Permissions: ${variable.name}`,
          canPickMany: true,
        });
        if (!writeRoles) return;
        writeRoleIds = new Set(writeRoles.map((r) => r.roleId));
      }

      // Build permissions array
      const permissions = roles
        .filter((r) => readRoleIds.has(r.id) || writeRoleIds.has(r.id))
        .map((r) => ({
          role_id: r.id,
          can_read: readRoleIds.has(r.id),
          can_write: writeRoleIds.has(r.id),
        }));

      try {
        await apiClient.patch(`/teams/${teamId}/variables/${variable.id}/permissions`, {
          permissions,
        });
        showInfo(`Permissions updated for "${variable.name}"`);
      } catch (err) {
        logError("Failed to update permissions", err);
        showError("Failed to update permissions");
      }
    }),
  );
}

/** Extract team from a tree item (works for team, member-header, variable-header) */
function extractTeam(item: TreeItemData): TeamItem | undefined {
  if (item?.type === "team") return item.team;
  return undefined;
}

/** Extract teamId from various tree item types */
function extractTeamId(item: TreeItemData): string | undefined {
  if (!item) return undefined;
  switch (item.type) {
    case "team": return item.team.id;
    case "member-header":
    case "variable-header":
    case "member":
    case "variable":
      return item.teamId;
  }
}
