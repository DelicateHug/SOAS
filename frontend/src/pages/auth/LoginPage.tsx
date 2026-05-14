import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";
import { Shield } from "lucide-react";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState("");
  const [registrationOpen, setRegistrationOpen] = useState(false);
  const { login, verifyMfa, isLoading } = useAuthStore();
  const navigate = useNavigate();

  const [providers, setProviders] = useState<{ password: boolean; oidc: boolean; cert: boolean } | null>(null);

  useEffect(() => {
    api.get<{ open: boolean }>("/auth/registration-open").then((res) => {
      setRegistrationOpen(res.open);
    }).catch(() => {});
    api.get<{ password: boolean; oidc: boolean; cert: boolean }>("/auth/providers")
      .then(setProviders)
      .catch(() => setProviders({ password: true, oidc: false, cert: false }));
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const result = await login(username.trim(), password);
      if (result.mfa_required && result.mfa_token) {
        setMfaToken(result.mfa_token);
      } else if (result.must_reset_password) {
        navigate("/change-password");
      } else {
        navigate("/dashboard");
      }
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      setError(apiErr.detail || "Login failed");
    }
  };

  const handleMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const result = await verifyMfa(mfaToken!, totpCode);
      if (result.must_reset_password) {
        navigate("/change-password");
      } else {
        navigate("/dashboard");
      }
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      setError(apiErr.detail || "Invalid code");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
      <div className="w-full max-w-sm p-8 border border-[var(--color-border)] rounded-lg">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Shield className="w-8 h-8 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold">SOAS</h1>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md bg-red-50 text-red-700 text-sm">
            {error}
          </div>
        )}

        {mfaToken ? (
          <form onSubmit={handleMfa} className="space-y-4">
            <p className="text-sm text-[var(--color-text-muted)] text-center">
              Enter the code from your authenticator app
            </p>
            <input
              type="text"
              placeholder="6-digit code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              maxLength={6}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md text-center text-lg tracking-widest"
              autoFocus
            />
            <button
              type="submit"
              disabled={isLoading || totpCode.length !== 6}
              className="w-full py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 disabled:opacity-50"
            >
              {isLoading ? "Verifying..." : "Verify"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Username or Email</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 disabled:opacity-50"
            >
              {isLoading ? "Signing in..." : "Sign In"}
            </button>
            {registrationOpen && (
              <p className="text-center text-sm text-[var(--color-text-muted)]">
                Don't have an account?{" "}
                <Link to="/register" className="text-[var(--color-primary)] hover:underline">
                  Register
                </Link>
              </p>
            )}
            {providers?.oidc && (
              <>
                <div className="relative my-2">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-[var(--color-border)]" />
                  </div>
                  <div className="relative flex justify-center">
                    <span className="px-2 text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)]">
                      or
                    </span>
                  </div>
                </div>
                <a
                  href="/api/v1/auth/oidc/start"
                  className="block w-full py-2 text-center rounded-md border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface-2)] text-sm font-medium"
                >
                  Sign in with Microsoft
                </a>
              </>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
