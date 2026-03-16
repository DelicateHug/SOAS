/**
 * @soas Chat Participant.
 * Provides AI-assisted SOC operations using VSCode's Language Model API.
 * Supports multi-turn tool calling with proper result feeding.
 */

import * as vscode from "vscode";
import type { AuthManager } from "../auth/authManager";
import { log, logError } from "../utils/notifications";
import { getActiveGraphEditorPanel } from "../panels/basePanel";

const MAX_TOOL_ROUNDS = 8;

function buildSystemPrompt(activeGraphContext: string | null): string {
  let prompt = `You are SOAS Assistant, an AI helper for SOC on a Stick — a Security Operations Center platform.

You can help with:
1. **Automation building**: Generate visual automation graphs from natural language descriptions. Use the soas_getNodeCatalog tool to understand available node types, then generate VP2GraphData JSON.
2. **Wiki content**: Generate documentation, playbooks, and post-mortems. Use soas_searchWiki and soas_getWikiPage to understand existing content.
3. **Incident analysis**: Investigate incidents by reviewing their details, timeline, and related data. Use soas_getIncident and soas_listIncidents.
4. **SOC operations**: Run automations, create incidents, and search for information.
5. **Graph editing**: When a graph editor is open, use soas_getCurrentGraph to see the current state and soas_updateAutomationGraph to modify it. You can add nodes, remove nodes, and rewire connections.

When generating or modifying automations:
- Always fetch the node catalog first to understand available node types
- Generate valid VP2GraphData JSON format with nodes and connections
- Include a "start" node as the entry point
- Connect nodes with proper flow (exec) and data connections
- Set node positions for a clean left-to-right layout (increment x by ~300 per column)
- When modifying an existing graph, fetch the current state first with soas_getCurrentGraph, then send the full updated graph via soas_updateAutomationGraph

When generating wiki content:
- Use markdown format
- Include relevant sections: Overview, Steps, Examples, References
- Reference existing wiki pages when appropriate

Always be concise and action-oriented. SOC analysts need quick, accurate responses.`;

  if (activeGraphContext) {
    prompt += `\n\n**Active Context**: A graph editor is currently open. ${activeGraphContext}`;
  }

  return prompt;
}

export function registerChatParticipant(
  context: vscode.ExtensionContext,
  authManager: AuthManager
): void {
  const participant = vscode.chat.createChatParticipant("soas.assistant", async (
    request: vscode.ChatRequest,
    chatContext: vscode.ChatContext,
    stream: vscode.ChatResponseStream,
    token: vscode.CancellationToken
  ) => {
    if (!authManager.isAuthenticated) {
      stream.markdown("You need to log in to SOAS first. Use the **SOAS: Login** command.");
      return;
    }

    try {
      // Select available language model
      const models = await vscode.lm.selectChatModels({
        vendor: "copilot",
        family: "gpt-4o",
      });

      let model = models[0];
      if (!model) {
        const allModels = await vscode.lm.selectChatModels();
        model = allModels[0];
      }

      if (!model) {
        stream.markdown("No language model available. Please ensure you have GitHub Copilot or another AI extension installed.");
        return;
      }

      // Check if a graph editor is active and inject context
      let activeGraphContext: string | null = null;
      const activePanel = getActiveGraphEditorPanel();
      if (activePanel) {
        activeGraphContext = `Automation ID: ${activePanel.automationId ?? "unsaved"}. Use soas_getCurrentGraph to see its nodes and connections, and soas_updateAutomationGraph to modify them.`;
      }

      // Build messages
      const messages: vscode.LanguageModelChatMessage[] = [
        vscode.LanguageModelChatMessage.User(buildSystemPrompt(activeGraphContext)),
      ];

      // Add conversation history
      for (const turn of chatContext.history) {
        if (turn instanceof vscode.ChatRequestTurn) {
          messages.push(vscode.LanguageModelChatMessage.User(turn.prompt));
        } else if (turn instanceof vscode.ChatResponseTurn) {
          const text = turn.response
            .map((part) => {
              if (part instanceof vscode.ChatResponseMarkdownPart) {
                return part.value.value;
              }
              return "";
            })
            .join("");
          if (text) {
            messages.push(vscode.LanguageModelChatMessage.Assistant(text));
          }
        }
      }

      // Add current request
      messages.push(vscode.LanguageModelChatMessage.User(request.prompt));

      const tools = await getAvailableTools();

      // Multi-turn tool calling loop
      for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
        const chatResponse = await model.sendRequest(messages, { tools }, token);

        // Collect the full response (text + tool calls)
        const textParts: string[] = [];
        const toolCalls: vscode.LanguageModelToolCallPart[] = [];

        for await (const part of chatResponse.stream) {
          if (part instanceof vscode.LanguageModelTextPart) {
            stream.markdown(part.value);
            textParts.push(part.value);
          } else if (part instanceof vscode.LanguageModelToolCallPart) {
            toolCalls.push(part);
          }
        }

        // If no tool calls, we're done — the model gave its final answer
        if (toolCalls.length === 0) {
          break;
        }

        // Add assistant message with text + tool calls to conversation
        const assistantParts: (vscode.LanguageModelTextPart | vscode.LanguageModelToolCallPart)[] = [];
        const fullText = textParts.join("");
        if (fullText) {
          assistantParts.push(new vscode.LanguageModelTextPart(fullText));
        }
        assistantParts.push(...toolCalls);
        messages.push(vscode.LanguageModelChatMessage.Assistant(assistantParts));

        // Invoke each tool and collect results
        for (const toolCall of toolCalls) {
          log(`AI requesting tool: ${toolCall.name}`);
          stream.progress(`Running ${toolCall.name}...`);

          try {
            const toolResult = await vscode.lm.invokeTool(
              toolCall.name,
              { input: toolCall.input, toolInvocationToken: request.toolInvocationToken },
              token
            );

            // Feed tool result back as a User message with ToolResultPart
            messages.push(
              vscode.LanguageModelChatMessage.User([
                new vscode.LanguageModelToolResultPart(toolCall.callId, toolResult.content),
              ])
            );

            log(`Tool ${toolCall.name} completed (callId: ${toolCall.callId})`);
          } catch (err) {
            logError(`Tool ${toolCall.name} invocation failed`, err);
            // Send error result so the model knows the tool failed
            messages.push(
              vscode.LanguageModelChatMessage.User([
                new vscode.LanguageModelToolResultPart(toolCall.callId, [
                  new vscode.LanguageModelTextPart(
                    `Error invoking ${toolCall.name}: ${err instanceof Error ? err.message : String(err)}`
                  ),
                ]),
              ])
            );
          }
        }

        // Loop continues — model will process tool results and respond
      }
    } catch (err) {
      logError("Chat participant error", err);
      stream.markdown(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  participant.iconPath = vscode.Uri.joinPath(context.extensionUri, "resources", "soas-icon.svg");

  context.subscriptions.push(participant);
}

async function getAvailableTools(): Promise<vscode.LanguageModelChatTool[]> {
  return [
    { name: "soas_listIncidents", description: "List incidents from SOAS" },
    { name: "soas_getIncident", description: "Get incident details with timeline" },
    { name: "soas_listAutomations", description: "List automations from SOAS" },
    { name: "soas_getNodeCatalog", description: "Get available node types for automation building" },
    { name: "soas_getAutomationGraph", description: "Get automation graph data by ID" },
    { name: "soas_getCurrentGraph", description: "Get the graph data from the currently open graph editor panel" },
    { name: "soas_updateAutomationGraph", description: "Update the graph in the currently open graph editor with new VP2GraphData JSON (nodes, connections, positions)" },
    { name: "soas_searchWiki", description: "Search wiki pages" },
    { name: "soas_getWikiPage", description: "Get wiki page content by slug" },
    { name: "soas_runAutomation", description: "Execute an automation" },
    { name: "soas_createIncident", description: "Create a new incident" },
  ];
}
