import * as vscode from "vscode";

/** Read extension configuration values */
export function getConfig() {
  const config = vscode.workspace.getConfiguration("soas");
  return {
    serverUrl: config.get<string>("serverUrl", "http://localhost:8000"),
    autoRefreshInterval: config.get<number>("autoRefreshInterval", 30),
    devMode: config.get<boolean>("devMode", false),
  };
}

/** Get a specific config value */
export function getServerUrl(): string {
  return vscode.workspace.getConfiguration("soas").get<string>("serverUrl", "http://localhost:8000");
}
