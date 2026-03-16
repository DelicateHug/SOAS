/**
 * Language Model Tools for the @soas chat participant.
 * These tools allow the AI to interact with the SOAS backend.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import { logError, log } from "../utils/notifications";
import { getActiveGraphEditorPanel } from "../panels/basePanel";

export function registerChatTools(
  context: vscode.ExtensionContext,
  _authManager: AuthManager
): void {
  // List Incidents
  context.subscriptions.push(
    vscode.lm.registerTool("soas_listIncidents", {
      async invoke(
        options: vscode.LanguageModelToolInvocationOptions,
        _token: vscode.CancellationToken
      ) {
        try {
          const input = options.input as { severity?: string; status?: string; page?: number };
          let url = `/incidents?per_page=20&page=${input.page || 1}`;
          if (input.severity) url += `&severity=${input.severity}`;
          if (input.status) url += `&status=${input.status}`;

          const result = await apiClient.get<unknown>(url);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_listIncidents failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Get Incident Details
  context.subscriptions.push(
    vscode.lm.registerTool("soas_getIncident", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { incidentId: string };
          const [incident, timeline] = await Promise.all([
            apiClient.get<unknown>(`/incidents/${input.incidentId}`),
            apiClient.get<unknown>(`/incidents/${input.incidentId}/timeline`),
          ]);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify({ incident, timeline }, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_getIncident failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // List Automations
  context.subscriptions.push(
    vscode.lm.registerTool("soas_listAutomations", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { status?: string; page?: number };
          let url = `/automations?per_page=20&page=${input.page || 1}`;
          if (input.status) url += `&status=${input.status}`;

          const result = await apiClient.get<unknown>(url);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_listAutomations failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Get Node Catalog
  context.subscriptions.push(
    vscode.lm.registerTool("soas_getNodeCatalog", {
      async invoke(_options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const result = await apiClient.get<unknown>("/graph-editor/node-catalog");
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_getNodeCatalog failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Get Automation Graph
  context.subscriptions.push(
    vscode.lm.registerTool("soas_getAutomationGraph", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { automationId: string };
          const result = await apiClient.get<unknown>(`/automations/${input.automationId}`);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_getAutomationGraph failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Search Wiki
  context.subscriptions.push(
    vscode.lm.registerTool("soas_searchWiki", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { query: string };
          const result = await apiClient.get<unknown>(`/wiki/search?q=${encodeURIComponent(input.query)}`);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_searchWiki failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Get Wiki Page
  context.subscriptions.push(
    vscode.lm.registerTool("soas_getWikiPage", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { slug: string };
          const result = await apiClient.get<unknown>(`/wiki/by-slug/${input.slug}`);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_getWikiPage failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Run Automation
  context.subscriptions.push(
    vscode.lm.registerTool("soas_runAutomation", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { automationId: string; parameters?: Record<string, unknown> };
          const result = await apiClient.post<unknown>(`/automations/${input.automationId}/execute`, {
            parameters: input.parameters,
          });
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_runAutomation failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Create Incident
  context.subscriptions.push(
    vscode.lm.registerTool("soas_createIncident", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { title: string; severity: string; summary?: string };
          const result = await apiClient.post<unknown>("/incidents", {
            title: input.title,
            severity: input.severity,
            summary: input.summary,
          });
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(result, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_createIncident failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Get Current Graph — reads the graph state from the active graph editor webview
  context.subscriptions.push(
    vscode.lm.registerTool("soas_getCurrentGraph", {
      async invoke(_options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const panel = getActiveGraphEditorPanel();
          if (!panel) {
            return new vscode.LanguageModelToolResult([
              new vscode.LanguageModelTextPart("No graph editor is currently open. Open an automation in the graph editor first."),
            ]);
          }

          log("Requesting graph state from active graph editor panel");
          const graphState = await panel.requestGraphState();
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(JSON.stringify(graphState, null, 2)),
          ]);
        } catch (err) {
          logError("Tool soas_getCurrentGraph failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );

  // Update Automation Graph — pushes new VP2GraphData to the active graph editor webview
  context.subscriptions.push(
    vscode.lm.registerTool("soas_updateAutomationGraph", {
      async invoke(options: vscode.LanguageModelToolInvocationOptions, _token: vscode.CancellationToken) {
        try {
          const input = options.input as { graphData: unknown };
          const panel = getActiveGraphEditorPanel();
          if (!panel) {
            return new vscode.LanguageModelToolResult([
              new vscode.LanguageModelTextPart("No graph editor is currently open. Open an automation in the graph editor first."),
            ]);
          }

          if (!input.graphData) {
            return new vscode.LanguageModelToolResult([
              new vscode.LanguageModelTextPart("Missing required parameter: graphData (VP2GraphData JSON with nodes and connections)"),
            ]);
          }

          log("Pushing graph data to active graph editor panel");
          panel.pushGraphData(input.graphData);

          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart("Graph updated successfully in the editor. The changes are marked as unsaved — the user can review and save them."),
          ]);
        } catch (err) {
          logError("Tool soas_updateAutomationGraph failed", err);
          return new vscode.LanguageModelToolResult([
            new vscode.LanguageModelTextPart(`Error: ${err instanceof Error ? err.message : String(err)}`),
          ]);
        }
      },
    })
  );
}
