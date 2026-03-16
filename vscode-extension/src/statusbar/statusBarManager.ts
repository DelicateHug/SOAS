/**
 * Status bar items for connection status and team selector.
 * A team must ALWAYS be selected — there is no "all teams" view.
 */

import * as vscode from "vscode";
import type { AuthManager } from "../auth/authManager";
import { apiClient } from "../api/client";
import { STATE_KEYS } from "../constants";
import { getServerUrl } from "../utils/config";
import { logError } from "../utils/notifications";

interface TeamListItem {
  id: string;
  name: string;
}

interface PaginatedTeams {
  data: TeamListItem[];
  meta: { total: number };
}

export class StatusBarManager implements vscode.Disposable {
  private connectionItem: vscode.StatusBarItem;
  private teamItem: vscode.StatusBarItem;
  private devModeItem: vscode.StatusBarItem;
  private globalState: vscode.Memento;
  private disposables: vscode.Disposable[] = [];

  private activeTeamId: string | undefined;
  private activeTeamName: string | undefined;

  private readonly _onDidChangeTeam = new vscode.EventEmitter<string | undefined>();
  readonly onDidChangeTeam = this._onDidChangeTeam.event;

  constructor(
    private readonly authManager: AuthManager,
    context: vscode.ExtensionContext
  ) {
    this.globalState = context.globalState;

    // Connection status (left side)
    this.connectionItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    this.connectionItem.command = "workbench.action.openSettings";
    this.connectionItem.tooltip = "SOAS Connection Status";

    // Team selector (left side, after connection)
    this.teamItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 99);
    this.teamItem.command = "soas.switchTeam";

    // Dev mode toggle (left side, after team)
    this.devModeItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 98);
    this.devModeItem.command = "soas.toggleDevMode";

    // Restore saved state
    this.activeTeamId = this.globalState.get(STATE_KEYS.ACTIVE_TEAM_ID);
    this.activeTeamName = this.globalState.get(STATE_KEYS.ACTIVE_TEAM_NAME);

    // React to auth changes
    this.disposables.push(
      this.authManager.onDidChangeState((state) => {
        this.update(state === "authenticated");
        // Auto-select a team when first authenticated if none is set
        if (state === "authenticated" && !this.activeTeamId) {
          this.autoSelectDefaultTeam();
        }
      })
    );

    // Register commands
    this.disposables.push(
      vscode.commands.registerCommand("soas.switchTeam", () => this.showTeamPicker()),
      vscode.commands.registerCommand("soas.toggleDevMode", () => this.toggleDevMode()),
    );
  }

  update(authenticated: boolean): void {
    if (authenticated) {
      const url = getServerUrl();
      const host = new URL(url).host;
      this.connectionItem.text = `$(shield) SOAS: ${host}`;
      this.connectionItem.backgroundColor = undefined;
      this.connectionItem.show();

      this.teamItem.text = `$(organization) ${this.activeTeamName || "No team"}`;
      this.teamItem.tooltip = "Click to switch team";
      this.teamItem.show();

      this.updateDevModeDisplay();
      this.devModeItem.show();
    } else {
      this.connectionItem.text = "$(shield) SOAS: Not connected";
      this.connectionItem.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
      this.connectionItem.show();

      this.teamItem.hide();
      this.devModeItem.hide();
    }
  }

  /** Refresh the dev mode status bar display (called from extension.ts on config change) */
  refreshDevMode(): void {
    this.updateDevModeDisplay();
  }

  private updateDevModeDisplay(): void {
    if (apiClient.devMode) {
      this.devModeItem.text = "$(beaker) Dev Mode";
      this.devModeItem.tooltip = "Dev Mode ON — saves go directly to automations. Click to switch to Production.";
      this.devModeItem.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
    } else {
      this.devModeItem.text = "$(lock) Production";
      this.devModeItem.tooltip = "Production Mode — saves create change requests. Click to switch to Dev Mode.";
      this.devModeItem.backgroundColor = undefined;
    }
  }

  private async toggleDevMode(): Promise<void> {
    const newMode = !apiClient.devMode;
    // Update the VSCode setting — the onDidChangeConfiguration handler in extension.ts
    // will pick this up and call apiClient.setDevMode() + set context key
    await vscode.workspace.getConfiguration("soas").update("devMode", newMode, vscode.ConfigurationTarget.Global);
    // Also update immediately for responsiveness
    apiClient.setDevMode(newMode);
    this.updateDevModeDisplay();
    vscode.window.showInformationMessage(
      newMode
        ? "Switched to Dev Mode — saves go directly to automations"
        : "Switched to Production Mode — saves create change requests"
    );
  }

  /** Update connection indicator based on health check */
  updateConnection(connected: boolean): void {
    if (!this.authManager.isAuthenticated) return;
    const url = getServerUrl();
    const host = new URL(url).host;
    if (connected) {
      this.connectionItem.text = `$(shield) SOAS: ${host}`;
      this.connectionItem.backgroundColor = undefined;
    } else {
      this.connectionItem.text = `$(shield) SOAS: ${host} (offline)`;
      this.connectionItem.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
    }
  }

  getActiveTeamId(): string | undefined {
    return this.activeTeamId;
  }

  /** Programmatically set the active team (e.g., from Teams tree view) */
  async setActiveTeam(teamId: string, teamName: string): Promise<void> {
    this.activeTeamId = teamId;
    this.activeTeamName = teamName;

    await this.globalState.update(STATE_KEYS.ACTIVE_TEAM_ID, this.activeTeamId);
    await this.globalState.update(STATE_KEYS.ACTIVE_TEAM_NAME, this.activeTeamName);

    this.teamItem.text = `$(organization) ${this.activeTeamName}`;
    this._onDidChangeTeam.fire(this.activeTeamId);
  }

  /** Auto-select the default team (or first available) when no team is set */
  async autoSelectDefaultTeam(): Promise<void> {
    try {
      const result = await apiClient.get<PaginatedTeams>("/teams?per_page=100");
      const teams = result.data;
      if (teams.length === 0) return;

      // Prefer team named "default", otherwise first
      const defaultTeam = teams.find((t) => t.name === "default") || teams[0];
      this.activeTeamId = defaultTeam.id;
      this.activeTeamName = defaultTeam.name;

      await this.globalState.update(STATE_KEYS.ACTIVE_TEAM_ID, this.activeTeamId);
      await this.globalState.update(STATE_KEYS.ACTIVE_TEAM_NAME, this.activeTeamName);

      this.teamItem.text = `$(organization) ${this.activeTeamName}`;
      this._onDidChangeTeam.fire(this.activeTeamId);
    } catch {
      // Non-fatal — user can pick manually
    }
  }

  private async showTeamPicker(): Promise<void> {
    try {
      const result = await apiClient.get<PaginatedTeams>("/teams?per_page=100");
      const teams = result.data;

      if (teams.length === 0) {
        vscode.window.showInformationMessage("You are not a member of any teams.");
        return;
      }

      const items: vscode.QuickPickItem[] = teams.map((t) => ({
        label: `$(organization) ${t.name}`,
        description: t.id === this.activeTeamId ? "(current)" : undefined,
        detail: t.id,
      }));

      const selected = await vscode.window.showQuickPick(items, {
        placeHolder: "Select a team to scope all data views",
        title: "Switch Team",
      });

      if (!selected) return;

      const team = teams.find((t) => t.id === selected.detail);
      if (team) {
        this.activeTeamId = team.id;
        this.activeTeamName = team.name;
      }

      await this.globalState.update(STATE_KEYS.ACTIVE_TEAM_ID, this.activeTeamId);
      await this.globalState.update(STATE_KEYS.ACTIVE_TEAM_NAME, this.activeTeamName);

      this.teamItem.text = `$(organization) ${this.activeTeamName}`;
      this._onDidChangeTeam.fire(this.activeTeamId);
    } catch (err) {
      logError("Failed to fetch teams", err);
    }
  }

  dispose(): void {
    this.connectionItem.dispose();
    this.teamItem.dispose();
    this.devModeItem.dispose();
    this._onDidChangeTeam.dispose();
    this.disposables.forEach((d) => d.dispose());
  }
}
