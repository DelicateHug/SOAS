/**
 * Backend health check — periodically pings the server and updates the status bar.
 * Fires an event when connectivity changes so the UI can react.
 */

import * as vscode from "vscode";
import { getServerUrl } from "../utils/config";
import { log, logError } from "../utils/notifications";

export class HealthCheckService implements vscode.Disposable {
  private timer: ReturnType<typeof setInterval> | undefined;
  private _isConnected = false;

  private readonly _onDidChangeConnection = new vscode.EventEmitter<boolean>();
  readonly onDidChangeConnection = this._onDidChangeConnection.event;

  get isConnected(): boolean {
    return this._isConnected;
  }

  start(): void {
    this.stop();
    this.check();
    this.timer = setInterval(() => this.check(), 60_000);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }
  }

  async check(): Promise<boolean> {
    const url = getServerUrl();
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5_000);
      const resp = await fetch(`${url}/api/v1/health`, { signal: controller.signal });
      clearTimeout(timeout);

      const connected = resp.ok;
      if (connected !== this._isConnected) {
        this._isConnected = connected;
        this._onDidChangeConnection.fire(connected);
        log(`Backend connectivity: ${connected ? "connected" : "disconnected"}`);
      }
      return connected;
    } catch {
      if (this._isConnected) {
        this._isConnected = false;
        this._onDidChangeConnection.fire(false);
        log("Backend connectivity: disconnected");
      }
      return false;
    }
  }

  dispose(): void {
    this.stop();
    this._onDidChangeConnection.dispose();
  }
}
