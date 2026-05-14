/**
 * Auth settings panel, mounted inside the Danger Zone page.
 *
 * Lets an admin flip the three auth providers (password, cert, OIDC),
 * paste Entra tenant + client id + redirect URI, and configure the
 * group → role mapping. Every mutation goes through PUT
 * /admin/danger-zone/auth-settings which writes a security_event.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Eye, EyeOff } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

type AuthSettings = Record<string, string>;

const TOGGLE_KEYS = [
  { key: "auth_password_enabled", label: "Allow username + password login", boolean: true },
  { key: "auth_cert_login_enabled", label: "Require client cert at the gateway", boolean: true },
  { key: "auth_oidc_enabled", label: "Enable Microsoft Entra (OIDC) login", boolean: true },
] as const;

interface StringSetting {
  key: string;
  label: string;
  placeholder: string;
  multiline?: boolean;
}

const STRING_KEYS: StringSetting[] = [
  {
    key: "auth_oidc_tenant",
    label: "Entra tenant id",
    placeholder: "00000000-0000-0000-0000-000000000000 or yourdomain.onmicrosoft.com",
  },
  { key: "auth_oidc_client_id", label: "Entra app (client) id", placeholder: "GUID" },
  {
    key: "auth_oidc_redirect_uri",
    label: "Redirect URI registered with Entra",
    placeholder: "https://soas.example.com/api/v1/auth/oidc/callback",
  },
  {
    key: "auth_oidc_group_mappings",
    label: "Entra group → SOAS role mappings (JSON)",
    placeholder: '{"<entra_oid>": "soc_manager"}',
    multiline: true,
  },
];

const CAE_KEYS = [
  { key: "auth_cae_cache_seconds", label: "CAE cache TTL (seconds)", placeholder: "30" },
  { key: "auth_cae_strict", label: "Fail closed if Entra CAE unreachable (true/false)", placeholder: "true", boolean: true },
] as const;

export function AdminAuthSettingsPanel() {
  const qc = useQueryClient();
  const [showSecret, setShowSecret] = useState(false);
  const [secretValue, setSecretValue] = useState("");

  const { data: settings } = useQuery({
    queryKey: ["auth-settings"],
    queryFn: () => api.get<AuthSettings>("/admin/danger-zone/auth-settings"),
  });

  const update = useMutation({
    mutationFn: (body: { key: string; value: string }) =>
      api.put<{ ok: boolean }>("/admin/danger-zone/auth-settings", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth-settings"] }),
  });

  if (!settings) {
    return (
      <Card>
        <CardBody>
          <div className="text-sm text-[var(--color-text-muted)]">Loading auth settings…</div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">Authentication</h3>
          <span className="text-xs text-[var(--color-text-muted)]">
            Every change here writes a security event.
          </span>
        </div>

        <div className="space-y-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              Providers
            </div>
            <div className="space-y-2">
              {TOGGLE_KEYS.map((t) => {
                const current = (settings[t.key] || "false").toLowerCase() === "true";
                return (
                  <label key={t.key} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={current}
                      onChange={(e) =>
                        update.mutate({ key: t.key, value: e.target.checked ? "true" : "false" })
                      }
                    />
                    <span>{t.label}</span>
                    <code className="text-[10px] text-[var(--color-text-muted)] font-mono ml-auto">
                      {t.key}
                    </code>
                  </label>
                );
              })}
            </div>
          </div>

          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              Microsoft Entra (OIDC)
            </div>
            <div className="space-y-2">
              {STRING_KEYS.map((s) => (
                <div key={s.key}>
                  <label className="block text-[11px] text-[var(--color-text-muted)] mb-1">
                    {s.label}
                  </label>
                  {s.multiline ? (
                    <textarea
                      defaultValue={settings[s.key] || ""}
                      onBlur={(e) => {
                        const v = e.target.value;
                        if (v !== (settings[s.key] || "")) update.mutate({ key: s.key, value: v });
                      }}
                      placeholder={s.placeholder}
                      rows={4}
                      className="w-full px-2 py-1.5 text-xs border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
                    />
                  ) : (
                    <input
                      defaultValue={settings[s.key] || ""}
                      onBlur={(e) => {
                        const v = e.target.value;
                        if (v !== (settings[s.key] || "")) update.mutate({ key: s.key, value: v });
                      }}
                      placeholder={s.placeholder}
                      className="w-full px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
                    />
                  )}
                </div>
              ))}

              {/* Client secret is write-only. Server returns "***" if set, empty otherwise. */}
              <div>
                <label className="block text-[11px] text-[var(--color-text-muted)] mb-1">
                  Entra client secret (write-only — current:{" "}
                  <span className="font-mono">{settings["auth_oidc_client_secret"] ? "set" : "(unset)"}</span>)
                </label>
                <div className="flex gap-1">
                  <div className="relative flex-1">
                    <input
                      type={showSecret ? "text" : "password"}
                      value={secretValue}
                      onChange={(e) => setSecretValue(e.target.value)}
                      placeholder="Paste new client secret"
                      className="w-full pr-8 px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowSecret((v) => !v)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
                    >
                      {showSecret ? <EyeOff size={12} /> : <Eye size={12} />}
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      if (!secretValue) return;
                      update.mutate(
                        { key: "auth_oidc_client_secret", value: secretValue },
                        {
                          onSuccess: () => setSecretValue(""),
                        },
                      );
                    }}
                    disabled={!secretValue}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
                  >
                    <Save size={12} /> Save
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] mb-2">
              Continuous Access Evaluation (CAE)
            </div>
            <div className="space-y-2">
              {CAE_KEYS.map((c) => (
                <div key={c.key}>
                  <label className="block text-[11px] text-[var(--color-text-muted)] mb-1">
                    {c.label}
                  </label>
                  <input
                    defaultValue={settings[c.key] || ""}
                    onBlur={(e) => {
                      const v = e.target.value;
                      if (v !== (settings[c.key] || "")) update.mutate({ key: c.key, value: v });
                    }}
                    placeholder={c.placeholder}
                    className="w-full px-2 py-1.5 text-sm border border-[var(--color-border)] rounded bg-[var(--color-surface)] font-mono"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
