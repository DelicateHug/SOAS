/**
 * SOC on a Stick - VSCode Extension entry point.
 */

import * as vscode from "vscode";
import { AuthManager } from "./auth/authManager";
import { LoginWebviewProvider } from "./auth/loginWebview";
import { StatusBarManager } from "./statusbar/statusBarManager";
import { IncidentTreeProvider } from "./providers/incidentTreeProvider";
import { CaseTreeProvider } from "./providers/caseTreeProvider";
import { AutomationTreeProvider } from "./providers/automationTreeProvider";
import { WikiTreeProvider } from "./providers/wikiTreeProvider";
import { ExecutionTreeProvider } from "./providers/executionTreeProvider";
import { IssueTreeProvider } from "./providers/issueTreeProvider";
import { registerIncidentCommands } from "./commands/incidents";
import { registerCaseCommands } from "./commands/cases";
import { registerAutomationCommands } from "./commands/automations";
import { registerWikiCommands } from "./commands/wiki";
import { registerExecutionCommands } from "./commands/executions";
import { registerAiCommands } from "./commands/ai";
import { registerIssueCommands } from "./commands/issues";
import { registerAdminCommands } from "./commands/admin";
import { registerTeamCommands } from "./commands/teams";
import { registerChatParticipant } from "./ai/chatParticipant";
import { registerChatTools } from "./ai/tools";
import { AdminTreeProvider } from "./providers/adminTreeProvider";
import { TeamTreeProvider } from "./providers/teamTreeProvider";
import { BasePanel } from "./panels/basePanel";
import { VIEW_IDS, CONTEXT_KEYS } from "./constants";
import { getConfig } from "./utils/config";
import { apiClient } from "./api/client";
import { log, showOutputChannel } from "./utils/notifications";
import { NotificationService } from "./services/notificationService";
import { HealthCheckService } from "./services/healthCheck";
import { startLocalBridge, stopLocalBridge, onBridgeMutation } from "./services/localBridge";
import { ensureClaudeCodeMcpConfig } from "./services/claudeCodeMcp";

export async function activate(context: vscode.ExtensionContext) {
  log("SOAS extension activating...");

  // --- Core services ---
  const authManager = new AuthManager(context);
  const statusBar = new StatusBarManager(authManager, context);

  // Dev mode from config
  const config = getConfig();
  apiClient.setDevMode(config.devMode);
  vscode.commands.executeCommand("setContext", CONTEXT_KEYS.DEV_MODE, config.devMode);
  statusBar.refreshDevMode();

  // Watch for config changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("soas.devMode")) {
        const devMode = getConfig().devMode;
        apiClient.setDevMode(devMode);
        vscode.commands.executeCommand("setContext", CONTEXT_KEYS.DEV_MODE, devMode);
        statusBar.refreshDevMode();
        BasePanel.broadcastDevMode(devMode);
      }
    })
  );

  // --- Login webview (shown when not authenticated) ---
  const loginProvider = new LoginWebviewProvider(context.extensionUri, authManager);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(VIEW_IDS.WELCOME, loginProvider)
  );

  // --- TreeView providers ---
  const incidentTree = new IncidentTreeProvider(authManager, statusBar);
  const caseTree = new CaseTreeProvider(authManager, statusBar);
  const automationTree = new AutomationTreeProvider(authManager, statusBar);
  const wikiTree = new WikiTreeProvider(authManager, statusBar);
  const executionTree = new ExecutionTreeProvider(authManager);
  const issueTree = new IssueTreeProvider(authManager);
  const adminTree = new AdminTreeProvider(authManager);
  const teamTree = new TeamTreeProvider(authManager, statusBar);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider(VIEW_IDS.INCIDENTS, incidentTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.CASES, caseTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.AUTOMATIONS, automationTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.WIKI, wikiTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.EXECUTIONS, executionTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.ISSUES, issueTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.ADMIN, adminTree),
    vscode.window.registerTreeDataProvider(VIEW_IDS.TEAMS, teamTree)
  );

  // Refresh all trees on team change
  statusBar.onDidChangeTeam(() => {
    incidentTree.refresh();
    caseTree.refresh();
    automationTree.refresh();
    teamTree.refresh();
  });

  // Refresh all trees on auth change
  authManager.onDidChangeState((state) => {
    if (state === "authenticated") {
      incidentTree.refresh();
      caseTree.refresh();
      automationTree.refresh();
      wikiTree.refresh();
      executionTree.refresh();
      issueTree.refresh();
      teamTree.refresh();
    }
  });

  // Auto-refresh timer
  let refreshInterval: ReturnType<typeof setInterval> | undefined;
  function startAutoRefresh() {
    stopAutoRefresh();
    const seconds = getConfig().autoRefreshInterval;
    if (seconds > 0) {
      refreshInterval = setInterval(() => {
        if (authManager.isAuthenticated) {
          incidentTree.refresh();
          executionTree.refresh();
        }
      }, seconds * 1000);
    }
  }
  function stopAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = undefined;
    }
  }

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("soas.autoRefreshInterval")) {
        startAutoRefresh();
      }
    })
  );

  // --- Commands ---
  registerIncidentCommands(context, incidentTree, authManager, statusBar);
  registerCaseCommands(context, caseTree, authManager, statusBar);
  registerAutomationCommands(context, automationTree, authManager);
  registerWikiCommands(context, wikiTree, authManager);
  registerExecutionCommands(context, executionTree, authManager);
  registerIssueCommands(context, issueTree, authManager);
  registerAiCommands(context, authManager);
  registerAdminCommands(context, adminTree, authManager);

  // Team commands
  registerTeamCommands(context, teamTree, authManager, statusBar);

  // --- Services ---
  const notificationService = new NotificationService(authManager);
  const healthCheck = new HealthCheckService();

  healthCheck.onDidChangeConnection((connected) => {
    statusBar.updateConnection(connected);
  });

  // Global commands
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.login", () => {
      // Focus the welcome view which contains the login form
      vscode.commands.executeCommand("soas-welcome.focus");
    }),
    vscode.commands.registerCommand("soas.logout", async () => {
      await authManager.logout();
      statusBar.update(false);
    }),
    vscode.commands.registerCommand("soas.openDashboard", () => {
      BasePanel.createOrShow(context.extensionUri, "dashboard", "Dashboard", authManager);
    }),
    vscode.commands.registerCommand("soas.openMonitoring", () => {
      BasePanel.createOrShow(context.extensionUri, "monitoring", "Monitoring", authManager);
    }),
    vscode.commands.registerCommand("soas.showOutput", () => {
      showOutputChannel();
    })
  );

  // --- AI integration ---
  registerChatParticipant(context, authManager);
  registerChatTools(context, authManager);

  // --- Local bridge for Claude Code MCP integration ---
  startLocalBridge();
  context.subscriptions.push({ dispose: stopLocalBridge });

  // Refresh tree views when MCP tools create/update/delete resources via the bridge
  onBridgeMutation(() => {
    if (authManager.isAuthenticated) {
      incidentTree.refresh();
      caseTree.refresh();
      automationTree.refresh();
      wikiTree.refresh();
      executionTree.refresh();
      issueTree.refresh();
      teamTree.refresh();
    }
  });

  // Auto-configure Claude Code MCP server (user-scoped, idempotent)
  ensureClaudeCodeMcpConfig(context).catch((err) => log(`MCP auto-config skipped: ${err}`));

  // --- Disposables ---
  context.subscriptions.push(authManager, statusBar, notificationService, healthCheck, { dispose: stopAutoRefresh });

  // --- Initialize ---
  await authManager.initialize();
  statusBar.update(authManager.isAuthenticated);
  if (authManager.isAuthenticated) {
    startAutoRefresh();
    notificationService.start();
  }

  authManager.onDidChangeState((state) => {
    if (state === "authenticated") {
      startAutoRefresh();
      notificationService.start();
    } else {
      stopAutoRefresh();
      notificationService.stop();
    }
  });

  // Start health check immediately (doesn't require auth)
  healthCheck.start();

  log("SOAS extension activated");
}

export function deactivate() {
  log("SOAS extension deactivated");
}
