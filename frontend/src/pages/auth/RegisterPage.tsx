import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/api";
import { Shield } from "lucide-react";

export function RegisterPage() {
  const [form, setForm] = useState({
    username: "",
    email: "",
    display_name: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);
  const { register, login, isLoading } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    api.get<{ open: boolean }>("/auth/registration-open").then((res) => {
      if (!res.open) {
        navigate("/login", { replace: true });
      } else {
        setChecking(false);
      }
    }).catch(() => {
      navigate("/login", { replace: true });
    });
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const trimmedForm = {
      username: form.username.trim(),
      email: form.email.trim(),
      display_name: form.display_name.trim(),
      password: form.password,
    };
    try {
      await register(trimmedForm);
      await login(trimmedForm.username, trimmedForm.password);
      navigate("/dashboard");
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      setError(apiErr.detail || "Registration failed");
    }
  };

  if (checking) {
    return <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]" />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
      <div className="w-full max-w-sm p-8 border border-[var(--color-border)] rounded-lg">
        <div className="flex items-center justify-center gap-2 mb-8">
          <Shield className="w-8 h-8 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold">Register</h1>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md bg-red-50 text-red-700 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Username</label>
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
              required
              minLength={3}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Display Name</label>
            <input
              type="text"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
              required
              minLength={8}
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 disabled:opacity-50"
          >
            {isLoading ? "Creating account..." : "Create Account"}
          </button>
          <p className="text-center text-sm text-[var(--color-text-muted)]">
            Already have an account?{" "}
            <Link to="/login" className="text-[var(--color-primary)] hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
