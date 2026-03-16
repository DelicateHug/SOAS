/**
 * Login webview panel for authentication.
 * Rendered as a webview panel with a simple login form + MFA support.
 */

import * as vscode from "vscode";
import type { AuthManager } from "./authManager";
import { showError, showInfo } from "../utils/notifications";

export class LoginWebviewProvider implements vscode.WebviewViewProvider {
  static readonly viewType = "soas-welcome";
  private view?: vscode.WebviewView;

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly authManager: AuthManager
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView): void {
    this.view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.extensionUri],
    };

    webviewView.webview.html = this.getHtml();

    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.type) {
        case "login": {
          try {
            const result = await this.authManager.login(message.username, message.password);
            if (result.mfaRequired) {
              webviewView.webview.postMessage({ type: "mfa-required", mfaToken: result.mfaToken });
            } else if (result.mustResetPassword) {
              webviewView.webview.postMessage({ type: "must-reset-password" });
            } else {
              webviewView.webview.postMessage({ type: "login-success" });
              showInfo(`Logged in as ${this.authManager.getUser()?.username}`);
            }
          } catch (err: unknown) {
            const msg = (err as { error?: string })?.error || "Login failed";
            webviewView.webview.postMessage({ type: "login-error", error: msg });
          }
          break;
        }
        case "verify-mfa": {
          try {
            const result = await this.authManager.verifyMfa(message.mfaToken, message.totpCode);
            if (result.mustResetPassword) {
              webviewView.webview.postMessage({ type: "must-reset-password" });
            } else {
              webviewView.webview.postMessage({ type: "login-success" });
              showInfo(`Logged in as ${this.authManager.getUser()?.username}`);
            }
          } catch (err: unknown) {
            const msg = (err as { error?: string })?.error || "MFA verification failed";
            webviewView.webview.postMessage({ type: "mfa-error", error: msg });
          }
          break;
        }
        case "change-password": {
          try {
            await this.authManager.login(message.username, message.newPassword);
            webviewView.webview.postMessage({ type: "login-success" });
          } catch {
            showError("Password change failed");
          }
          break;
        }
        case "open-settings": {
          vscode.commands.executeCommand("workbench.action.openSettings", "soas.serverUrl");
          break;
        }
      }
    });
  }

  private getHtml(): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: var(--vscode-font-family);
      color: var(--vscode-foreground);
      background: transparent;
      padding: 16px;
      margin: 0;
    }
    h2 {
      margin: 0 0 4px;
      font-size: 16px;
      font-weight: 600;
    }
    p.subtitle {
      margin: 0 0 16px;
      font-size: 12px;
      color: var(--vscode-descriptionForeground);
    }
    .form-group {
      margin-bottom: 12px;
    }
    label {
      display: block;
      margin-bottom: 4px;
      font-size: 12px;
      color: var(--vscode-foreground);
    }
    input {
      width: 100%;
      box-sizing: border-box;
      padding: 6px 8px;
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, transparent);
      border-radius: 2px;
      font-size: 13px;
      outline: none;
    }
    input:focus {
      border-color: var(--vscode-focusBorder);
    }
    button {
      width: 100%;
      padding: 8px;
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 2px;
      font-size: 13px;
      cursor: pointer;
      margin-top: 4px;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    button.secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    .error {
      color: var(--vscode-errorForeground);
      font-size: 12px;
      margin-top: 8px;
      display: none;
    }
    .error.visible {
      display: block;
    }
    .hidden {
      display: none;
    }
    .server-url {
      margin-top: 16px;
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      text-align: center;
    }
    .server-url a {
      color: var(--vscode-textLink-foreground);
      cursor: pointer;
      text-decoration: none;
    }
    .server-url a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <!-- Login Form -->
  <div id="login-form">
    <h2>SOC on a Stick</h2>
    <p class="subtitle">Sign in to your SOAS instance</p>

    <div class="form-group">
      <label for="username">Username</label>
      <input type="text" id="username" placeholder="Username" autofocus />
    </div>

    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" placeholder="Password" />
    </div>

    <div id="login-error" class="error"></div>

    <button id="login-btn">Sign In</button>

    <div class="server-url">
      <a id="settings-link">Configure server URL</a>
    </div>
  </div>

  <!-- MFA Form -->
  <div id="mfa-form" class="hidden">
    <h2>Two-Factor Authentication</h2>
    <p class="subtitle">Enter your TOTP code</p>

    <div class="form-group">
      <label for="totp-code">Authentication Code</label>
      <input type="text" id="totp-code" placeholder="6-digit code" maxlength="6" />
    </div>

    <div id="mfa-error" class="error"></div>

    <button id="mfa-btn">Verify</button>
    <button id="mfa-back" class="secondary" style="margin-top: 8px;">Back to Login</button>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    let mfaToken = null;

    // Elements
    const loginForm = document.getElementById('login-form');
    const mfaForm = document.getElementById('mfa-form');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginBtn = document.getElementById('login-btn');
    const loginError = document.getElementById('login-error');
    const totpInput = document.getElementById('totp-code');
    const mfaBtn = document.getElementById('mfa-btn');
    const mfaError = document.getElementById('mfa-error');
    const mfaBack = document.getElementById('mfa-back');
    const settingsLink = document.getElementById('settings-link');

    function showLoginError(msg) {
      loginError.textContent = msg;
      loginError.classList.add('visible');
    }

    function showMfaError(msg) {
      mfaError.textContent = msg;
      mfaError.classList.add('visible');
    }

    loginBtn.addEventListener('click', () => {
      loginError.classList.remove('visible');
      const username = usernameInput.value.trim();
      const password = passwordInput.value;
      if (!username || !password) {
        showLoginError('Username and password are required');
        return;
      }
      loginBtn.textContent = 'Signing in...';
      loginBtn.disabled = true;
      vscode.postMessage({ type: 'login', username, password });
    });

    passwordInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') loginBtn.click();
    });

    mfaBtn.addEventListener('click', () => {
      mfaError.classList.remove('visible');
      const code = totpInput.value.trim();
      if (!code) {
        showMfaError('Enter your authentication code');
        return;
      }
      mfaBtn.textContent = 'Verifying...';
      mfaBtn.disabled = true;
      vscode.postMessage({ type: 'verify-mfa', mfaToken, totpCode: code });
    });

    totpInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') mfaBtn.click();
    });

    mfaBack.addEventListener('click', () => {
      mfaForm.classList.add('hidden');
      loginForm.classList.remove('hidden');
      mfaToken = null;
      passwordInput.value = '';
    });

    settingsLink.addEventListener('click', () => {
      vscode.postMessage({ type: 'open-settings' });
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      switch (msg.type) {
        case 'mfa-required':
          mfaToken = msg.mfaToken;
          loginForm.classList.add('hidden');
          mfaForm.classList.remove('hidden');
          totpInput.focus();
          loginBtn.textContent = 'Sign In';
          loginBtn.disabled = false;
          break;
        case 'login-error':
          showLoginError(msg.error);
          loginBtn.textContent = 'Sign In';
          loginBtn.disabled = false;
          break;
        case 'mfa-error':
          showMfaError(msg.error);
          mfaBtn.textContent = 'Verify';
          mfaBtn.disabled = false;
          break;
        case 'login-success':
          // The view will be hidden by the when-clause
          break;
      }
    });
  </script>
</body>
</html>`;
  }
}
