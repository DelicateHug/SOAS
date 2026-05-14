import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import { BranchStatusBadge } from "@/components/ui/BranchStatusBadge";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { Shield, ShieldAlert, Fingerprint, Key, GitBranch, CheckCircle2, XCircle } from "lucide-react";
import type { GitSyncConfig, ChangeRequestDetail } from "@/types/api";

export function AdminSettingsPage() {
  const user = useAuthStore((s) => s.user);
  const { isDevMode } = useDeploymentMode();
  const { data: settingsCRs } = useQuery({
    queryKey: ["change-requests", "active", "app_settings"],
    queryFn: () => api.get<ChangeRequestDetail[]>("/change-requests/active?entity_type=app_settings"),
    enabled: isDevMode,
    staleTime: 10_000,
  });
  const hasSettingsCR = (settingsCRs?.length ?? 0) > 0;

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <h1 className="text-2xl font-bold">Security Settings</h1>
        {hasSettingsCR && settingsCRs?.[0] && (
          <BranchStatusBadge branchStatus="modified" changeRequest={settingsCRs[0]} />
        )}
      </div>

      <div className="space-y-6">
        <GitSyncSection />
        <LoginSecuritySection />
        <MfaSection isMfaEnabled={false} />
        <WebAuthnSection />
        <AccountInfoSection user={user} />
      </div>
    </div>
  );
}

const ALL_ENTITY_TYPES = [
  "automations",
  "wiki",
  "code_library",
  "settings",
  "roles",
  "form_definitions",
  "variables",
  "normalization",
  "webhook_sources",
  "incident_variables",
];

function GitSyncSection() {
  const queryClient = useQueryClient();
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [initResult, setInitResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);
  const [showImportConfirm, setShowImportConfirm] = useState(false);
  const [importResult, setImportResult] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const { data: config, isLoading } = useQuery({
    queryKey: ["git-sync-config"],
    queryFn: () => api.get<GitSyncConfig>("/git-sync/config"),
  });

  const [form, setForm] = useState<GitSyncConfig | null>(null);

  // Initialize form when config loads
  const currentForm = form ?? config;

  const saveMut = useToastMutation({
    mutationFn: (data: Partial<GitSyncConfig>) =>
      api.put("/git-sync/config", data),
    loadingMessage: "Saving git sync config...",
    successMessage: "Git sync configuration saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["git-sync-config"] });
      queryClient.invalidateQueries({ queryKey: ["git-sync-status"] });
      setForm(null);
    },
  });

  const testMut = useToastMutation({
    mutationFn: (data: {
      remote_url: string;
      auth_type: string;
      auth_token: string;
      ssh_key_path: string;
    }) => api.post<{ ok: boolean; message: string }>("/git-sync/test", data),
    loadingMessage: "Testing connection...",
    successMessage: false,
    errorMessage: false,
    onSuccess: (data) => setTestResult(data),
    onError: () =>
      setTestResult({ ok: false, message: "Connection test failed" }),
  });

  const initMut = useToastMutation({
    mutationFn: () =>
      api.post<{ ok: boolean; message: string }>("/git-sync/initialize", {}),
    loadingMessage: "Initializing repository...",
    successMessage: false,
    errorMessage: false,
    onSuccess: (data) => {
      setInitResult(data);
      queryClient.invalidateQueries({ queryKey: ["git-sync-status"] });
    },
    onError: () =>
      setInitResult({ ok: false, message: "Initialization failed" }),
  });

  const importMut = useToastMutation({
    mutationFn: () =>
      api.post<{
        id: string;
        status: string;
        entities_pulled: number;
        duration_ms: number;
      }>("/git-sync/import", {}),
    loadingMessage: "Importing from git...",
    successMessage: (data) => `Import complete: ${data.entities_pulled} entities imported.`,
    onSuccess: (data) => {
      setImportResult({
        ok: true,
        message: `Import complete: ${data.entities_pulled} entities imported in ${data.duration_ms}ms`,
      });
      setShowImportConfirm(false);
      queryClient.invalidateQueries({ queryKey: ["git-sync-status"] });
      queryClient.invalidateQueries({ queryKey: ["git-sync-config"] });
    },
    onError: () => {
      setImportResult({ ok: false, message: "Destructive import failed" });
      setShowImportConfirm(false);
    },
  });

  if (isLoading || !currentForm) {
    return (
      <div className="border border-[var(--color-border)] rounded-lg p-4">
        <p className="text-[var(--color-text-muted)]">
          Loading git sync settings...
        </p>
      </div>
    );
  }

  const updateField = (key: keyof GitSyncConfig, value: string) => {
    setForm({ ...(form ?? config!), [key]: value });
  };

  const toggleEntityType = (et: string) => {
    const current = (currentForm.git_sync_entity_types || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const updated = current.includes(et)
      ? current.filter((e) => e !== et)
      : [...current, et];
    updateField("git_sync_entity_types", updated.join(","));
  };

  const enabledTypes = (currentForm.git_sync_entity_types || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const isEnabled = currentForm.git_sync_enabled === "true";

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center gap-3 mb-4">
        <GitBranch className="w-5 h-5 text-[var(--color-primary)]" />
        <div>
          <h2 className="font-semibold">Git Sync</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Sync persistent data to a Git repository for backup and GitOps
            workflows
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Enable toggle */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Enable Git Sync</span>
          <button
            onClick={() =>
              updateField(
                "git_sync_enabled",
                isEnabled ? "false" : "true"
              )
            }
            className={`relative w-11 h-6 rounded-full transition-colors ${
              isEnabled
                ? "bg-[var(--color-primary)]"
                : "bg-[var(--color-surface-2)]"
            }`}
          >
            <span
              className={`block w-5 h-5 rounded-full bg-white shadow transition-transform ${
                isEnabled ? "translate-x-5" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>

        {/* Remote URL */}
        <div>
          <label className="text-sm font-medium">Remote URL</label>
          <input
            value={currentForm.git_sync_remote_url}
            onChange={(e) =>
              updateField("git_sync_remote_url", e.target.value)
            }
            placeholder="https://github.com/org/soas-config.git (leave empty for local-only)"
            className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
          />
        </div>

        {/* Branch */}
        <div>
          <label className="text-sm font-medium">Branch</label>
          <input
            value={currentForm.git_sync_branch}
            onChange={(e) =>
              updateField("git_sync_branch", e.target.value)
            }
            placeholder="main"
            className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
          />
        </div>

        {/* Auth type */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-medium">Auth Type</label>
            <select
              value={currentForm.git_sync_auth_type}
              onChange={(e) =>
                updateField("git_sync_auth_type", e.target.value)
              }
              className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
            >
              <option value="token">Personal Access Token</option>
              <option value="ssh_key">SSH Key</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium">Sync Interval (sec)</label>
            <input
              type="number"
              min={300}
              value={currentForm.git_sync_interval_seconds}
              onChange={(e) =>
                updateField("git_sync_interval_seconds", e.target.value)
              }
              className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
            />
          </div>
        </div>

        {/* Auth credential */}
        {currentForm.git_sync_auth_type === "token" ? (
          <div>
            <label className="text-sm font-medium">Access Token</label>
            <input
              type="password"
              value={
                currentForm.git_sync_auth_token === "***"
                  ? ""
                  : currentForm.git_sync_auth_token
              }
              onChange={(e) =>
                updateField("git_sync_auth_token", e.target.value)
              }
              placeholder={
                config?.git_sync_auth_token === "***"
                  ? "Token is set (leave blank to keep)"
                  : "ghp_..."
              }
              className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
            />
          </div>
        ) : (
          <div>
            <label className="text-sm font-medium">SSH Key Path</label>
            <input
              value={currentForm.git_sync_ssh_key_path}
              onChange={(e) =>
                updateField("git_sync_ssh_key_path", e.target.value)
              }
              placeholder="/home/soas/.ssh/id_ed25519"
              className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
            />
          </div>
        )}

        {/* Entity types */}
        <div>
          <label className="text-sm font-medium mb-2 block">
            Entity Types to Sync
          </label>
          <div className="flex flex-wrap gap-2">
            {ALL_ENTITY_TYPES.map((et) => (
              <button
                key={et}
                onClick={() => toggleEntityType(et)}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  enabledTypes.includes(et)
                    ? "bg-[var(--color-primary)] text-[#ffffff] border-[var(--color-primary)]"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)]"
                }`}
              >
                {et.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--color-border)]">
          <button
            onClick={() => {
              const toSave: Partial<GitSyncConfig> = {};
              if (form) {
                // Only send fields that changed (or all if form was touched)
                Object.entries(form).forEach(([k, v]) => {
                  // Don't send masked token
                  if (k === "git_sync_auth_token" && (v === "***" || v === "")) return;
                  (toSave as Record<string, string>)[k] = v;
                });
              }
              saveMut.mutate(toSave);
            }}
            disabled={!form || saveMut.isPending}
            className="px-4 py-2 text-sm rounded-md bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50"
          >
            {saveMut.isPending ? "Saving..." : "Save Configuration"}
          </button>
          <button
            onClick={() => {
              setTestResult(null);
              testMut.mutate({
                remote_url: currentForm.git_sync_remote_url,
                auth_type: currentForm.git_sync_auth_type,
                auth_token:
                  currentForm.git_sync_auth_token === "***"
                    ? ""
                    : currentForm.git_sync_auth_token,
                ssh_key_path: currentForm.git_sync_ssh_key_path,
              });
            }}
            disabled={!currentForm.git_sync_remote_url || testMut.isPending}
            className="px-4 py-2 text-sm rounded-md border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)] disabled:opacity-50"
          >
            {testMut.isPending ? "Testing..." : "Test Connection"}
          </button>
          <button
            onClick={async () => {
              setInitResult(null);
              // Auto-save config before initializing
              if (form) {
                const toSave: Partial<GitSyncConfig> = {};
                Object.entries(form).forEach(([k, v]) => {
                  if (k === "git_sync_auth_token" && (v === "***" || v === "")) return;
                  (toSave as Record<string, string>)[k] = v;
                });
                try {
                  await api.put("/git-sync/config", toSave);
                  queryClient.invalidateQueries({ queryKey: ["git-sync-config"] });
                } catch {
                  setInitResult({ ok: false, message: "Failed to save config before initializing" });
                  return;
                }
              }
              initMut.mutate();
            }}
            disabled={initMut.isPending}
            className="px-4 py-2 text-sm rounded-md border border-[var(--color-border)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)] disabled:opacity-50"
          >
            {initMut.isPending ? "Initializing..." : "Initialize Repository"}
          </button>
          <button
            onClick={() => {
              setImportResult(null);
              setShowImportConfirm(true);
            }}
            disabled={importMut.isPending}
            className="px-4 py-2 text-sm rounded-md border border-red-500 text-red-600 hover:bg-red-50 dark:hover:bg-red-950 disabled:opacity-50"
          >
            {importMut.isPending ? "Importing..." : "Import from Git"}
          </button>
        </div>

        {/* Result messages */}
        {testResult && (
          <div
            className={`flex items-center gap-2 text-sm p-2 rounded ${
              testResult.ok
                ? "bg-green-500/10 text-green-600"
                : "bg-red-500/10 text-red-600"
            }`}
          >
            {testResult.ok ? (
              <CheckCircle2 className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            {testResult.message}
          </div>
        )}
        {initResult && (
          <div
            className={`flex items-center gap-2 text-sm p-2 rounded ${
              initResult.ok
                ? "bg-green-500/10 text-green-600"
                : "bg-red-500/10 text-red-600"
            }`}
          >
            {initResult.ok ? (
              <CheckCircle2 className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            {initResult.message}
          </div>
        )}
        {importResult && (
          <div
            className={`flex items-center gap-2 text-sm p-2 rounded ${
              importResult.ok
                ? "bg-green-500/10 text-green-600"
                : "bg-red-500/10 text-red-600"
            }`}
          >
            {importResult.ok ? (
              <CheckCircle2 className="w-4 h-4" />
            ) : (
              <XCircle className="w-4 h-4" />
            )}
            {importResult.message}
          </div>
        )}
      </div>

      {/* Destructive import confirmation modal */}
      {showImportConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl w-[440px] p-6">
            <h3 className="text-sm font-semibold text-red-600 mb-2">
              Destructive Import
            </h3>
            <p className="text-sm text-[var(--color-text-muted)] mb-3">
              This will <strong>permanently delete all existing data</strong>{" "}
              for the configured entity types and replace it with the contents
              of the git repository. This action cannot be undone.
            </p>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Entity types that will be replaced:{" "}
              <span className="font-medium">
                {enabledTypes.join(", ") || "none configured"}
              </span>
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowImportConfirm(false)}
                className="px-4 py-2 text-sm rounded-md border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
              >
                Cancel
              </button>
              <button
                onClick={() => importMut.mutate()}
                disabled={importMut.isPending}
                className="px-4 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {importMut.isPending
                  ? "Importing..."
                  : "Yes, Delete All & Import"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LoginSecuritySection() {
  const queryClient = useQueryClient();

  const { data: maxAttempts, isLoading: loadingMax } = useQuery({
    queryKey: ["settings", "max_failed_login_attempts"],
    queryFn: () =>
      api.get<{ key: string; value: string }>(
        "/settings/max_failed_login_attempts"
      ),
  });

  const { data: lockoutMin, isLoading: loadingLockout } = useQuery({
    queryKey: ["settings", "failed_login_lockout_minutes"],
    queryFn: () =>
      api.get<{ key: string; value: string }>(
        "/settings/failed_login_lockout_minutes"
      ),
  });

  const [maxAttemptsVal, setMaxAttemptsVal] = useState<string | null>(null);
  const [lockoutMinVal, setLockoutMinVal] = useState<string | null>(null);

  const currentMax = maxAttemptsVal ?? maxAttempts?.value ?? "";
  const currentLockout = lockoutMinVal ?? lockoutMin?.value ?? "";

  const isDirty =
    maxAttemptsVal !== null || lockoutMinVal !== null;

  const saveMut = useToastMutation({
    mutationFn: async () => {
      const promises: Promise<unknown>[] = [];
      if (maxAttemptsVal !== null) {
        promises.push(
          api.put("/settings/max_failed_login_attempts", {
            value: maxAttemptsVal,
          })
        );
      }
      if (lockoutMinVal !== null) {
        promises.push(
          api.put("/settings/failed_login_lockout_minutes", {
            value: lockoutMinVal,
          })
        );
      }
      await Promise.all(promises);
    },
    loadingMessage: "Saving login security settings...",
    successMessage: "Login security settings saved.",
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["settings", "max_failed_login_attempts"],
      });
      queryClient.invalidateQueries({
        queryKey: ["settings", "failed_login_lockout_minutes"],
      });
      setMaxAttemptsVal(null);
      setLockoutMinVal(null);
    },
  });

  if (loadingMax || loadingLockout) {
    return (
      <div className="border border-[var(--color-border)] rounded-lg p-4">
        <p className="text-[var(--color-text-muted)]">
          Loading login security settings...
        </p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center gap-3 mb-4">
        <ShieldAlert className="w-5 h-5 text-[var(--color-primary)]" />
        <div>
          <h2 className="font-semibold">Login Security</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Configure account lockout after failed login attempts
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-medium">
              Max Failed Attempts
            </label>
            <input
              type="number"
              min={0}
              value={currentMax}
              onChange={(e) => setMaxAttemptsVal(e.target.value)}
              className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
            />
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              0 = no lockout
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">
              Lockout Duration (minutes)
            </label>
            <input
              type="number"
              min={1}
              value={currentLockout}
              onChange={(e) => setLockoutMinVal(e.target.value)}
              className="w-full mt-1 px-3 py-2 border border-[var(--color-border)] rounded-md text-sm bg-transparent"
            />
          </div>
        </div>

        <div className="flex gap-2 pt-2 border-t border-[var(--color-border)]">
          <button
            onClick={() => saveMut.mutate()}
            disabled={!isDirty || saveMut.isPending}
            className="px-4 py-2 text-sm rounded-md bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50"
          >
            {saveMut.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function MfaSection({ isMfaEnabled }: { isMfaEnabled: boolean }) {
  const [step, setStep] = useState<"idle" | "setup" | "verify">("idle");
  const [qrUri, setQrUri] = useState("");
  const [secret, setSecret] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState("");

  const setupMfa = useToastMutation({
    mutationFn: () => api.post<{ secret: string; totp_uri: string }>("/auth/mfa/setup"),
    loadingMessage: "Setting up MFA...",
    successMessage: false,
    onSuccess: (data) => {
      setQrUri(data.totp_uri);
      setSecret(data.secret);
      setStep("verify");
    },
  });

  const verifySetup = useToastMutation({
    mutationFn: () => api.post("/auth/mfa/verify-setup", { totp_code: totpCode }),
    loadingMessage: false,
    successMessage: "MFA enabled successfully.",
    errorMessage: false,
    onSuccess: () => {
      setStep("idle");
      setTotpCode("");
    },
    onError: () => setError("Invalid code. Please try again."),
  });

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <Key className="w-5 h-5 text-[var(--color-primary)]" />
        <div>
          <h2 className="font-semibold">Two-Factor Authentication (TOTP)</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Add an extra layer of security using an authenticator app
          </p>
        </div>
      </div>

      {step === "idle" && (
        <div className="flex items-center justify-between">
          <span className={`px-2 py-0.5 rounded text-xs ${
            isMfaEnabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"
          }`}>
            {isMfaEnabled ? "Enabled" : "Not configured"}
          </span>
          {!isMfaEnabled && (
            <button
              onClick={() => setupMfa.mutate()}
              disabled={setupMfa.isPending}
              className="px-3 py-1.5 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm"
            >
              {setupMfa.isPending ? "Setting up..." : "Enable MFA"}
            </button>
          )}
        </div>
      )}

      {step === "verify" && (
        <div className="space-y-3 mt-3">
          <p className="text-sm">
            Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.):
          </p>
          <div className="bg-white p-4 rounded-lg inline-block">
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUri)}`}
              alt="TOTP QR Code"
              className="w-48 h-48"
            />
          </div>
          <p className="text-xs text-[var(--color-text-muted)]">
            Or enter manually: <code className="px-1 bg-[var(--color-surface-2)] rounded">{secret}</code>
          </p>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={totpCode}
              onChange={(e) => { setTotpCode(e.target.value); setError(""); }}
              placeholder="Enter 6-digit code"
              maxLength={6}
              className="px-3 py-2 border border-[var(--color-border)] rounded-md w-40 font-mono"
            />
            <button
              onClick={() => verifySetup.mutate()}
              disabled={totpCode.length !== 6 || verifySetup.isPending}
              className="px-3 py-2 bg-green-600 text-white rounded-md text-sm disabled:opacity-50"
            >
              Verify
            </button>
            <button
              onClick={() => { setStep("idle"); setTotpCode(""); setError(""); }}
              className="px-3 py-2 border border-[var(--color-border)] rounded-md text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function WebAuthnSection() {
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const registerWebAuthn = useToastMutation({
    mutationFn: async () => {
      // Step 1: Get registration options from server
      const options = await api.post<PublicKeyCredentialCreationOptions>(
        "/auth/webauthn/register/begin"
      );

      // Step 2: Create credential using browser API
      const credential = await navigator.credentials.create({
        publicKey: {
          ...options,
          challenge: Uint8Array.from(atob(options.challenge as unknown as string), (c) => c.charCodeAt(0)),
          user: {
            ...options.user,
            id: Uint8Array.from(atob((options.user as unknown as { id: string }).id), (c) => c.charCodeAt(0)),
          },
        },
      });

      if (!credential) throw new Error("Registration cancelled");

      // Step 3: Send credential to server for verification
      const attestationResponse = credential as PublicKeyCredential;
      const response = attestationResponse.response as AuthenticatorAttestationResponse;

      return api.post("/auth/webauthn/register/complete", {
        id: attestationResponse.id,
        raw_id: btoa(String.fromCharCode(...new Uint8Array(attestationResponse.rawId))),
        response: {
          attestation_object: btoa(
            String.fromCharCode(...new Uint8Array(response.attestationObject))
          ),
          client_data_json: btoa(
            String.fromCharCode(...new Uint8Array(response.clientDataJSON))
          ),
        },
        type: attestationResponse.type,
      });
    },
    loadingMessage: "Registering passkey...",
    successMessage: "Passkey registered successfully.",
    errorMessage: false,
    onSuccess: () => {
      setStatus("Passkey registered successfully!");
      setError("");
    },
    onError: (err: Error) => {
      setError(err.message || "Registration failed");
      setStatus("");
    },
  });

  const supportsWebAuthn = typeof window !== "undefined" && !!window.PublicKeyCredential;

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <Fingerprint className="w-5 h-5 text-[var(--color-primary)]" />
        <div>
          <h2 className="font-semibold">Windows Hello / Passkey</h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Use biometric or PIN authentication for passwordless login
          </p>
        </div>
      </div>

      {!supportsWebAuthn ? (
        <p className="text-sm text-[var(--color-text-muted)]">
          WebAuthn is not supported in this browser.
        </p>
      ) : (
        <div>
          {status && <p className="text-sm text-green-600 mb-2">{status}</p>}
          {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
          <button
            onClick={() => registerWebAuthn.mutate()}
            disabled={registerWebAuthn.isPending}
            className="px-3 py-1.5 bg-[var(--color-primary)] text-[#ffffff] rounded-md text-sm"
          >
            {registerWebAuthn.isPending ? "Registering..." : "Register Passkey"}
          </button>
        </div>
      )}
    </div>
  );
}

function AccountInfoSection({ user }: { user: { id: string; username: string; display_name: string; email: string; roles: string[] } | null }) {
  if (!user) return null;

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <Shield className="w-5 h-5 text-[var(--color-primary)]" />
        <h2 className="font-semibold">Account Info</h2>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-[var(--color-text-muted)] text-xs">Username</p>
          <p className="font-medium">@{user.username}</p>
        </div>
        <div>
          <p className="text-[var(--color-text-muted)] text-xs">Display Name</p>
          <p className="font-medium">{user.display_name}</p>
        </div>
        <div>
          <p className="text-[var(--color-text-muted)] text-xs">Roles</p>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {user.roles.map((role) => (
              <span key={role} className="px-1.5 py-0.5 bg-[var(--color-surface-2)] rounded text-xs">
                {role}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
