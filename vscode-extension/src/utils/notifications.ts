import * as vscode from "vscode";

const OUTPUT_CHANNEL = vscode.window.createOutputChannel("SOAS");

export function log(message: string): void {
  const timestamp = new Date().toISOString();
  OUTPUT_CHANNEL.appendLine(`[${timestamp}] ${message}`);
}

export function logError(message: string, error?: unknown): void {
  const timestamp = new Date().toISOString();
  const errorStr = error instanceof Error ? error.message : String(error ?? "");
  OUTPUT_CHANNEL.appendLine(`[${timestamp}] ERROR: ${message} ${errorStr}`);
}

export function showInfo(message: string): void {
  vscode.window.showInformationMessage(message);
}

export function showError(message: string): void {
  vscode.window.showErrorMessage(message);
}

export function showWarning(message: string): void {
  vscode.window.showWarningMessage(message);
}

export function showOutputChannel(): void {
  OUTPUT_CHANNEL.show();
}
