/**
 * Authentication manager using VSCode SecretStorage.
 * Handles login, token refresh, MFA, and session state.
 */

import * as vscode from "vscode";
import { SECRET_KEYS, CONTEXT_KEYS } from "../constants";
import { apiClient, type TokenProvider } from "../api/client";
import { log, logError, showError, showInfo } from "../utils/notifications";

interface JwtPayload {
  sub: string;
  username: string;
  display_name?: string;
  roles: string[];
  permissions: string[];
  teams: Array<{ id: string; name: string; roles: string[]; team_role: string }>;
  exp: number;
  iat: number;
}

export interface UserInfo {
  id: string;
  username: string;
  displayName: string;
  roles: string[];
  permissions: string[];
  teams: Array<{ id: string; name: string; roles: string[]; team_role: string }>;
}

type AuthState = "authenticated" | "unauthenticated";

export class AuthManager implements TokenProvider, vscode.Disposable {
  private readonly _onDidChangeState = new vscode.EventEmitter<AuthState>();
  readonly onDidChangeState = this._onDidChangeState.event;

  private secretStorage: vscode.SecretStorage;
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;
  private currentUser: UserInfo | null = null;
  private disposed = false;

  constructor(context: vscode.ExtensionContext) {
    this.secretStorage = context.secrets;
    apiClient.setTokenProvider(this);
  }

  /** Initialize: check for stored tokens and restore session */
  async initialize(): Promise<void> {
    const token = await this.getAccessToken();
    if (token) {
      try {
        const payload = this.parseJwt(token);
        if (payload.exp * 1000 > Date.now()) {
          this.setUserFromPayload(payload);
          this.scheduleRefresh(payload.exp);
          await this.setAuthContext(true);
          log(`Session restored for ${payload.username}`);
          return;
        }
      } catch {
        // Token invalid, try refresh
      }

      // Try refreshing
      const refreshToken = await this.getRefreshToken();
      if (refreshToken) {
        try {
          const refreshed = await this.refreshSession();
          if (refreshed) return;
        } catch {
          // Refresh failed
        }
      }

      await this.clearTokens();
    }

    await this.setAuthContext(false);
  }

  /** Login with username and password */
  async login(
    username: string,
    password: string
  ): Promise<{ mfaRequired?: boolean; mfaToken?: string; mustResetPassword?: boolean }> {
    // Clear stale tokens before login attempt
    await this.clearTokens();

    const res = await apiClient.post<Record<string, unknown>>("/auth/login", {
      username,
      password,
    });

    if (res.mfa_required) {
      return { mfaRequired: true, mfaToken: res.mfa_token as string };
    }

    const { access_token, refresh_token, must_reset_password } = res as {
      access_token: string;
      refresh_token: string;
      must_reset_password?: boolean;
    };

    await this.setTokens(access_token, refresh_token);
    const payload = this.parseJwt(access_token);
    this.setUserFromPayload(payload);
    this.scheduleRefresh(payload.exp);
    await this.setAuthContext(true);
    log(`Login successful for ${username}`);

    return { mustResetPassword: must_reset_password === true };
  }

  /** Verify MFA TOTP code */
  async verifyMfa(
    mfaToken: string,
    totpCode: string
  ): Promise<{ mustResetPassword?: boolean }> {
    const res = await apiClient.post<{
      access_token: string;
      refresh_token: string;
      must_reset_password?: boolean;
    }>("/auth/mfa/verify", { mfa_token: mfaToken, totp_code: totpCode });

    await this.setTokens(res.access_token, res.refresh_token);
    const payload = this.parseJwt(res.access_token);
    this.setUserFromPayload(payload);
    this.scheduleRefresh(payload.exp);
    await this.setAuthContext(true);

    return { mustResetPassword: res.must_reset_password === true };
  }

  /** Logout and clear all stored credentials */
  async logout(): Promise<void> {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Best-effort logout
    }
    await this.clearTokens();
    this.currentUser = null;
    this.cancelRefresh();
    await this.setAuthContext(false);
    log("Logged out");
  }

  /** Refresh the current session */
  async refreshSession(): Promise<boolean> {
    const refreshToken = await this.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await apiClient.post<{
        access_token: string;
        refresh_token: string;
      }>("/auth/refresh", { refresh_token: refreshToken });

      await this.setTokens(res.access_token, res.refresh_token);
      const payload = this.parseJwt(res.access_token);
      this.setUserFromPayload(payload);
      this.scheduleRefresh(payload.exp);
      await this.setAuthContext(true);
      log("Session refreshed");
      return true;
    } catch (err) {
      logError("Session refresh failed", err);
      await this.clearTokens();
      this.currentUser = null;
      await this.setAuthContext(false);
      return false;
    }
  }

  /** Get current authenticated user info */
  getUser(): UserInfo | null {
    return this.currentUser;
  }

  /** Check if user has a specific permission */
  hasPermission(permission: string): boolean {
    if (!this.currentUser) return false;
    if (this.currentUser.roles.includes("admin")) return true;
    return this.currentUser.permissions.includes(permission);
  }

  /** Check if user has a specific role */
  hasRole(role: string): boolean {
    return this.currentUser?.roles.includes(role) ?? false;
  }

  get isAuthenticated(): boolean {
    return this.currentUser !== null;
  }

  // --- TokenProvider interface ---

  async getAccessToken(): Promise<string | undefined> {
    return this.secretStorage.get(SECRET_KEYS.ACCESS_TOKEN);
  }

  async getRefreshToken(): Promise<string | undefined> {
    return this.secretStorage.get(SECRET_KEYS.REFRESH_TOKEN);
  }

  async setTokens(access: string, refresh: string): Promise<void> {
    await this.secretStorage.store(SECRET_KEYS.ACCESS_TOKEN, access);
    await this.secretStorage.store(SECRET_KEYS.REFRESH_TOKEN, refresh);
  }

  async clearTokens(): Promise<void> {
    await this.secretStorage.delete(SECRET_KEYS.ACCESS_TOKEN);
    await this.secretStorage.delete(SECRET_KEYS.REFRESH_TOKEN);
  }

  onSessionExpired(): void {
    this.currentUser = null;
    this.cancelRefresh();
    this.setAuthContext(false);
    showError("SOAS session expired. Please login again.");
    this._onDidChangeState.fire("unauthenticated");
  }

  // --- Private helpers ---

  private parseJwt(token: string): JwtPayload {
    const base64Url = token.split(".")[1]!;
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const json = Buffer.from(base64, "base64").toString("utf-8");
    return JSON.parse(json);
  }

  private setUserFromPayload(payload: JwtPayload): void {
    this.currentUser = {
      id: payload.sub,
      username: payload.username,
      displayName: payload.display_name || payload.username,
      roles: payload.roles || [],
      permissions: payload.permissions || [],
      teams: payload.teams || [],
    };
  }

  private scheduleRefresh(expTimestamp: number): void {
    this.cancelRefresh();
    // Refresh 60 seconds before expiry
    const refreshAt = expTimestamp * 1000 - 60_000;
    const delay = Math.max(refreshAt - Date.now(), 5000);

    this.refreshTimer = setTimeout(async () => {
      if (this.disposed) return;
      const success = await this.refreshSession();
      if (!success) {
        this.onSessionExpired();
      }
    }, delay);
  }

  private cancelRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }

  private async setAuthContext(authenticated: boolean): Promise<void> {
    await vscode.commands.executeCommand("setContext", CONTEXT_KEYS.IS_AUTHENTICATED, authenticated);
    const isAdmin = this.currentUser?.roles.includes("admin") ?? false;
    await vscode.commands.executeCommand("setContext", CONTEXT_KEYS.IS_ADMIN, isAdmin);
    this._onDidChangeState.fire(authenticated ? "authenticated" : "unauthenticated");
  }

  dispose(): void {
    this.disposed = true;
    this.cancelRefresh();
    this._onDidChangeState.dispose();
  }
}
