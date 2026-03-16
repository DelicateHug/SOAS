/**
 * Auth state management with Zustand.
 */

import { create } from "zustand";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

interface TeamClaim {
  id: string;
  name: string;
  roles: string[];
  team_role: string;
}

interface User {
  id: string;
  username: string;
  display_name: string;
  email: string;
  roles: string[];
  permissions: string[];
  teams: TeamClaim[];
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mustResetPassword: boolean;
  tokenExpiresAt: number | null;
  isRefreshing: boolean;

  login: (username: string, password: string) => Promise<{ mfa_required?: boolean; mfa_token?: string; must_reset_password?: boolean }>;
  verifyMfa: (mfaToken: string, totpCode: string) => Promise<{ must_reset_password?: boolean }>;
  register: (data: { username: string; email: string; display_name: string; password: string }) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
  refreshSession: () => Promise<void>;
}

function parseJwt(token: string): Record<string, unknown> {
  const base64Url = token.split(".")[1]!;
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(base64));
}

function getTokenExpiration(token: string): number | null {
  try {
    const payload = parseJwt(token);
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set, get) => {
  // Initialize from stored token
  const storedToken = localStorage.getItem("access_token");
  let initialUser: User | null = null;
  let initialMustReset = false;
  let initialTokenExpiresAt: number | null = null;

  if (storedToken) {
    try {
      const payload = parseJwt(storedToken);
      initialUser = {
        id: payload.sub as string,
        username: payload.username as string,
        display_name: (payload.display_name as string) || (payload.username as string),
        email: "",
        roles: (payload.roles as string[]) || [],
        permissions: (payload.permissions as string[]) || [],
        teams: (payload.teams as TeamClaim[]) || [],
      };
      initialMustReset = localStorage.getItem("must_reset_password") === "true";
      initialTokenExpiresAt = getTokenExpiration(storedToken);
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("must_reset_password");
    }
  }

  // Sync tokenExpiresAt when api client refreshes tokens on 401
  api.setOnTokensChanged((accessToken) => {
    const exp = getTokenExpiration(accessToken);
    set({ tokenExpiresAt: exp });
  });

  return {
    user: initialUser,
    isAuthenticated: initialUser !== null,
    isLoading: false,
    mustResetPassword: initialMustReset,
    tokenExpiresAt: initialTokenExpiresAt,
    isRefreshing: false,

    login: async (username, password) => {
      // Clear any stale tokens so the API client doesn't try to refresh on 401
      api.clearTokens();
      set({ isLoading: true });
      try {
        const res = await api.post<Record<string, unknown>>("/auth/login", {
          username,
          password,
        });

        if (res.mfa_required) {
          return { mfa_required: true, mfa_token: res.mfa_token as string };
        }

        const { access_token, refresh_token, must_reset_password } = res as {
          access_token: string;
          refresh_token: string;
          must_reset_password?: boolean;
        };
        api.setTokens(access_token, refresh_token);

        const mustReset = must_reset_password === true;
        if (mustReset) {
          localStorage.setItem("must_reset_password", "true");
        } else {
          localStorage.removeItem("must_reset_password");
        }

        const payload = parseJwt(access_token);
        set({
          user: {
            id: payload.sub as string,
            username: payload.username as string,
            display_name: (payload.display_name as string) || (payload.username as string),
            email: "",
            roles: (payload.roles as string[]) || [],
            permissions: (payload.permissions as string[]) || [],
            teams: (payload.teams as TeamClaim[]) || [],
          },
          isAuthenticated: true,
          mustResetPassword: mustReset,
          tokenExpiresAt: typeof payload.exp === "number" ? payload.exp : null,
        });

        return { must_reset_password: mustReset };
      } finally {
        set({ isLoading: false });
      }
    },

    verifyMfa: async (mfaToken, totpCode) => {
      set({ isLoading: true });
      try {
        const res = await api.post<{ access_token: string; refresh_token: string; must_reset_password?: boolean }>(
          "/auth/mfa/verify",
          { mfa_token: mfaToken, totp_code: totpCode }
        );
        api.setTokens(res.access_token, res.refresh_token);

        const mustReset = res.must_reset_password === true;
        if (mustReset) {
          localStorage.setItem("must_reset_password", "true");
        } else {
          localStorage.removeItem("must_reset_password");
        }

        const payload = parseJwt(res.access_token);
        set({
          user: {
            id: payload.sub as string,
            username: payload.username as string,
            display_name: (payload.display_name as string) || (payload.username as string),
            email: "",
            roles: (payload.roles as string[]) || [],
            permissions: (payload.permissions as string[]) || [],
            teams: (payload.teams as TeamClaim[]) || [],
          },
          isAuthenticated: true,
          mustResetPassword: mustReset,
          tokenExpiresAt: typeof payload.exp === "number" ? payload.exp : null,
        });

        return { must_reset_password: mustReset };
      } finally {
        set({ isLoading: false });
      }
    },

    register: async (data) => {
      set({ isLoading: true });
      try {
        await api.post("/auth/register", data);
      } finally {
        set({ isLoading: false });
      }
    },

    changePassword: async (currentPassword, newPassword) => {
      set({ isLoading: true });
      try {
        await api.post("/auth/change-password", {
          current_password: currentPassword,
          new_password: newPassword,
        });
        localStorage.removeItem("must_reset_password");
        set({ mustResetPassword: false });
      } finally {
        set({ isLoading: false });
      }
    },

    logout: () => {
      api.clearTokens();
      localStorage.removeItem("must_reset_password");
      queryClient.clear();
      set({ user: null, isAuthenticated: false, mustResetPassword: false, tokenExpiresAt: null, isRefreshing: false });
    },

    hasPermission: (permission) => {
      const { user } = get();
      if (!user) return false;
      // Admin role bypasses all permission checks
      if (user.roles?.includes("admin")) return true;
      return user.permissions.includes(permission);
    },

    refreshSession: async () => {
      set({ isRefreshing: true });
      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) {
          get().logout();
          return;
        }

        const res = await fetch("/api/v1/auth/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });

        if (!res.ok) {
          get().logout();
          return;
        }

        const data = await res.json();
        api.setTokens(data.access_token, data.refresh_token);

        // Re-parse user from the new JWT so teams/permissions stay fresh
        const payload = parseJwt(data.access_token);
        set({
          user: {
            id: payload.sub as string,
            username: payload.username as string,
            display_name: (payload.display_name as string) || (payload.username as string),
            email: "",
            roles: (payload.roles as string[]) || [],
            permissions: (payload.permissions as string[]) || [],
            teams: (payload.teams as TeamClaim[]) || [],
          },
          tokenExpiresAt: typeof payload.exp === "number" ? payload.exp : null,
        });
      } catch {
        get().logout();
      } finally {
        set({ isRefreshing: false });
      }
    },
  };
});
