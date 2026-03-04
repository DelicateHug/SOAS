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

  useEffect(() => {
    api.get<{ open: boolean }>("/auth/registration-open").then((res) => {
      setRegistrationOpen(res.open);
    }).catch(() => {});
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const result = await login(username, password);
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
    <div className="min-h-screen flex items-center justify-center bg-[hsl(var(--background))]">
      <div className="w-full max-w-sm p-8 border border-[hsl(var(--border))] rounded-lg">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Shield className="w-8 h-8 text-[hsl(var(--primary))]" />
          <h1 className="text-2xl font-bold">SOAS</h1>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md bg-red-50 text-red-700 text-sm">
            {error}
          </div>
        )}

        {mfaToken ? (
          <form onSubmit={handleMfa} className="space-y-4">
            <p className="text-sm text-[hsl(var(--muted-foreground))] text-center">
              Enter the code from your authenticator app
            </p>
            <input
              type="text"
              placeholder="6-digit code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              maxLength={6}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-center text-lg tracking-widest"
              autoFocus
            />
            <button
              type="submit"
              disabled={isLoading || totpCode.length !== 6}
              className="w-full py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50"
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
                className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50"
            >
              {isLoading ? "Signing in..." : "Sign In"}
            </button>
            {registrationOpen && (
              <p className="text-center text-sm text-[hsl(var(--muted-foreground))]">
                Don't have an account?{" "}
                <Link to="/register" className="text-[hsl(var(--primary))] hover:underline">
                  Register
                </Link>
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
