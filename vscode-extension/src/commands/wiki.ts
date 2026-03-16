/**
 * Command handlers for wiki operations.
 */

import * as vscode from "vscode";
import { apiClient } from "../api/client";
import type { AuthManager } from "../auth/authManager";
import type { WikiTreeProvider } from "../providers/wikiTreeProvider";
import { BasePanel } from "../panels/basePanel";
import { showError, showInfo, logError } from "../utils/notifications";

interface WikiSearchResult {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
}

export function registerWikiCommands(
  context: vscode.ExtensionContext,
  tree: WikiTreeProvider,
  authManager: AuthManager
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("soas.wiki.refresh", () => {
      tree.refresh();
    }),

    vscode.commands.registerCommand("soas.wiki.create", async () => {
      const title = await vscode.window.showInputBox({
        prompt: "Wiki page title",
        placeHolder: "e.g., Incident Response Playbook",
      });
      if (!title) return;

      try {
        const result = await apiClient.post<{ id: string; slug: string }>("/wiki", {
          title,
          content: "",
          status: "draft",
        });
        showInfo(`Wiki page "${title}" created`);
        tree.refresh();
        BasePanel.createOrShow(
          context.extensionUri,
          "wikiEditor",
          title,
          authManager,
          { pageId: result.id, slug: result.slug }
        );
      } catch (err) {
        logError("Failed to create wiki page", err);
        showError("Failed to create wiki page");
      }
    }),

    vscode.commands.registerCommand("soas.wiki.openEditor", (page: { id: string; slug: string; title: string }) => {
      BasePanel.createOrShow(
        context.extensionUri,
        "wikiEditor",
        page.title || "Wiki Editor",
        authManager,
        { pageId: page.id, slug: page.slug }
      );
    }),

    vscode.commands.registerCommand("soas.wiki.search", async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Search wiki pages",
        placeHolder: "Enter search query...",
      });
      if (!query) return;

      try {
        const results = await apiClient.get<{ data: WikiSearchResult[] }>(
          `/wiki/search?q=${encodeURIComponent(query)}`
        );

        if (results.data.length === 0) {
          showInfo("No wiki pages found");
          return;
        }

        const selected = await vscode.window.showQuickPick(
          results.data.map((r) => ({
            label: r.title,
            description: r.slug,
            detail: r.excerpt,
            page: r,
          })),
          { placeHolder: `${results.data.length} results for "${query}"` }
        );

        if (selected) {
          BasePanel.createOrShow(
            context.extensionUri,
            "wikiEditor",
            selected.page.title,
            authManager,
            { pageId: selected.page.id, slug: selected.page.slug }
          );
        }
      } catch (err) {
        logError("Wiki search failed", err);
        showError("Wiki search failed");
      }
    })
  );
}
