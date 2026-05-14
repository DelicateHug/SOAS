/**
 * OIDC callback landing page.
 *
 * The backend's /auth/oidc/callback redirects here with a URL fragment
 * carrying the SOAS access token, e.g.:
 *   /oidc-callback#access_token=ey...&oidc=1
 *
 * The token is in the fragment (not query string) so it never reaches
 * the server log. We parse it client-side, hand it to authStore, then
 * redirect to /dashboard.
 */
import { useEffect, useState } from "react";
import { Shield, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";

export function OIDCCallbackPage() {
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const access = params.get("access_token");
    if (!access) {
      setErr("No access token in callback URL fragment.");
      return;
    }
    // Burn the fragment so the token isn't kept in the address bar.
    window.history.replaceState({}, "", window.location.pathname);

    // Stash the SOAS-issued token. No refresh token for OIDC sessions
    // today — when the access token expires, re-run the OIDC flow.
    api.setTokens(access, "");
    // Hard navigation so authStore re-initialises from localStorage and
    // bootstraps the user record on next paint.
    window.location.assign("/dashboard");
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-full max-w-md p-6 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] shadow">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="text-[var(--color-primary)]" size={20} />
          <h1 className="text-lg font-semibold">Signing you in…</h1>
        </div>
        {err ? (
          <div className="flex items-start gap-2 text-sm text-[var(--color-danger)]">
            <AlertTriangle size={16} className="mt-0.5" />
            <div>
              <div>Sign-in failed.</div>
              <div className="text-xs font-mono mt-1">{err}</div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-[var(--color-text-muted)]">
            Completing Microsoft sign-in…
          </div>
        )}
      </div>
    </div>
  );
}
