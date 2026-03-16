/**
 * Command handlers for incident operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { IncidentTreeProvider } from "../providers/incidentTreeProvider";
import type { StatusBarManager } from "../statusbar/statusBarManager";
import { BasePanel } from "../panels/basePanel";
import { showError, showInfo, logError } from "../utils/notifications";

const SEVERITIES = ["critical", "high", "medium", "low", "informational"];
const STATUSES = [
  "detected", "triaging", "investigating", "containing",
  "remediating", "resolved", "closed", "false_positive",
];

export function registerIncidentCommands(
  context: vscode.ExtensionContext,
  tree: IncidentTreeProvider,
  authManager: AuthManager,
  statusBar: StatusBarManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.incidents.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.incidents.create", async () => {
      const title = await vscode.window.showInputBox({
        prompt: "Incident title",
        placeHolder: "e.g., Suspicious login from unknown IP",
      });
      if (!title) return;

      const severity = await vscode.window.showQuickPick(SEVERITIES, {
        placeHolder: "Select severity",
      });
      if (!severity) return;

      const summary = await vscode.window.showInputBox({
        prompt: "Summary (optional)",
        placeHolder: "Brief description of the incident",
      });

      try {
        const teamId = statusBar.getActiveTeamId();
        await apiClient.post("/incidents", {
          title,
          severity,
          summary: summary || undefined,
          team_id: teamId || undefined,
        });
        showInfo(`Incident "${title}" created`);
        tree.refresh();
      } catch (err) {
        logError("Failed to create incident", err);
        showError("Failed to create incident");
      }
    }),

    vscode.commands.registerCommand("soas.incidents.open", (incident: { id: string }) => {
      BasePanel.createOrShow(
        context.extensionUri,
        "incidentDetail",
        "Incident",
        authManager,
        { incidentId: incident.id }
      );
    }),

    vscode.commands.registerCommand("soas.incidents.changeStatus", async (element: { kind: string; incident?: { id: string; status: string } }) => {
      const incident = element?.kind === "incident" ? element.incident : undefined;
      if (!incident) return;

      const newStatus = await vscode.window.showQuickPick(
        STATUSES.filter((s) => s !== incident.status),
        { placeHolder: `Current: ${incident.status}. Select new status:` }
      );
      if (!newStatus) return;

      try {
        await apiClient.post(`/incidents/${incident.id}/transition`, { status: newStatus });
        showInfo(`Incident status changed to ${newStatus}`);
        tree.refresh();
      } catch (err) {
        logError("Failed to change incident status", err);
        showError("Failed to change status");
      }
    }),

    vscode.commands.registerCommand("soas.incidents.filter", async () => {
      const filterType = await vscode.window.showQuickPick(
        [
          { label: "$(filter) Filter by Severity", detail: "severity" },
          { label: "$(filter) Filter by Status", detail: "status" },
          { label: "$(close) Clear Filters", detail: "clear" },
        ],
        { placeHolder: "Select filter type" }
      );
      if (!filterType) return;

      if (filterType.detail === "clear") {
        tree.setFilter(undefined, undefined);
        return;
      }

      if (filterType.detail === "severity") {
        const severity = await vscode.window.showQuickPick(SEVERITIES, {
          placeHolder: "Filter by severity",
        });
        if (severity) tree.setFilter(severity, undefined);
      } else {
        const status = await vscode.window.showQuickPick(STATUSES, {
          placeHolder: "Filter by status",
        });
        if (status) tree.setFilter(undefined, status);
      }
    })
  );
}
