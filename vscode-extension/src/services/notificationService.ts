/**
 * Notification service - polls for execution completions and new critical incidents.
 * Shows VSCode notifications when important events occur.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import { log, logError } from "../utils/notifications";

interface ExecutionSummary {
  id: string;
  status: string;
  automation_name?: string;
}

interface IncidentSummary {
  id: string;
  title: string;
  severity: string;
  created_at: string;
}

export class NotificationService implements vscode.Disposable {
  private pollTimer: ReturnType<typeof setInterval> | undefined;
  private knownExecutionIds = new Set<string>();
  private knownIncidentIds = new Set<string>();
  private initialized = false;

  constructor(private authManager: AuthManager) {}

  start(): void {
    this.stop();
    // Seed known IDs on first poll (don't notify for pre-existing items)
    this.initialized = false;
    this.poll();
    this.pollTimer = setInterval(() => this.poll(), 30_000);
  }

  stop(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = undefined;
    }
  }

  private async poll(): Promise<void> {
    if (!this.authManager.isAuthenticated) return;

    try {
      await Promise.all([
        this.checkExecutions(),
        this.checkCriticalIncidents(),
      ]);
      this.initialized = true;
    } catch {
      // Silently ignore poll errors — backend may be temporarily unreachable
    }
  }

  private async checkExecutions(): Promise<void> {
    try {
      const result = await apiClient.get<{ data: ExecutionSummary[] }>(
        "/executions?per_page=10&page=1"
      );
      const executions = result?.data || [];

      for (const exec of executions) {
        if (this.knownExecutionIds.has(exec.id)) {
          // Check if status changed to a terminal state
          continue;
        }
        this.knownExecutionIds.add(exec.id);

        if (!this.initialized) continue; // Don't notify on startup

        if (exec.status === "completed") {
          const action = await vscode.window.showInformationMessage(
            `Automation "${exec.automation_name || "Unknown"}" completed successfully.`,
            "View Output"
          );
          if (action === "View Output") {
            vscode.commands.executeCommand("soas.executions.view", { id: exec.id, automation_name: exec.automation_name });
          }
        } else if (exec.status === "failed") {
          const action = await vscode.window.showErrorMessage(
            `Automation "${exec.automation_name || "Unknown"}" failed.`,
            "View Output"
          );
          if (action === "View Output") {
            vscode.commands.executeCommand("soas.executions.view", { id: exec.id, automation_name: exec.automation_name });
          }
        }
      }

      // Prune old IDs to prevent memory growth
      if (this.knownExecutionIds.size > 200) {
        const ids = Array.from(this.knownExecutionIds);
        const currentIds = new Set(executions.map((e) => e.id));
        for (const id of ids) {
          if (!currentIds.has(id)) {
            this.knownExecutionIds.delete(id);
          }
        }
      }
    } catch (err) {
      logError("Notification poll: executions check failed", err);
    }
  }

  private async checkCriticalIncidents(): Promise<void> {
    try {
      const result = await apiClient.get<{ data: IncidentSummary[] }>(
        "/incidents?per_page=5&page=1&severity=critical&status=open"
      );
      const incidents = result?.data || [];

      for (const inc of incidents) {
        if (this.knownIncidentIds.has(inc.id)) continue;
        this.knownIncidentIds.add(inc.id);

        if (!this.initialized) continue;

        const action = await vscode.window.showWarningMessage(
          `New critical incident: ${inc.title}`,
          "Open Incident"
        );
        if (action === "Open Incident") {
          vscode.commands.executeCommand("soas.incidents.open", { id: inc.id });
        }
      }
    } catch (err) {
      logError("Notification poll: incidents check failed", err);
    }
  }

  dispose(): void {
    this.stop();
    log("Notification service disposed");
  }
}
