import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { Shield } from "lucide-react";

export function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const { changePassword, isLoading } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    try {
      await changePassword(currentPassword, newPassword);
      navigate("/dashboard");
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      setError(apiErr.detail || "Failed to change password");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
      <div className="w-full max-w-sm p-8 border border-[var(--color-border)] rounded-lg">
        <div className="flex items-center justify-center gap-2 mb-4">
          <Shield className="w-8 h-8 text-[var(--color-primary)]" />
          <h1 className="text-2xl font-bold">SOAS</h1>
        </div>

        <h2 className="text-lg font-semibold text-center mb-2">Password Reset Required</h2>
        <p className="text-sm text-[var(--color-text-muted)] text-center mb-6">
          You must change your password before continuing.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-md bg-red-50 text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Current Password</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-md"
              required
              minLength={8}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
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
            {isLoading ? "Changing..." : "Change Password"}
          </button>
        </form>
      </div>
    </div>
  );
}
