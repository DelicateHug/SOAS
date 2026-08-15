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
  /** True until the initial /auth/session/bootstrap call settles. ProtectedRoute should
   *  show a loading state instead of redirecting to /login while this is true — otherwise
   *  every page refresh bounces the user back to the login page before the cookie-backed
   *  session has a chance to re-hydrate. */
  isBootstrapping: boolean;
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
  /**
   * Pull the HMAC session key from /auth/session/bootstrap. Called after login, after
   * OIDC redirect, and on app mount when a cookie is present. Returns true if the session
   * is alive, false otherwise (caller should redirect to /login).
   */
  bootstrapAppSession: () => Promise<boolean>;
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
  // Browser auth = httpOnly soas_session cookie + in-memory HMAC key.
  // No localStorage credentials. The cookie is session-scope (browser-close kills it)
  // and the server-side AppToken caps the absolute TTL at 6h. Page reload re-bootstraps
  // identity from /auth/session/bootstrap (works as long as the cookie is still alive).
  const initialUser: User | null = null;
  const initialMustReset = localStorage.getItem("must_reset_password") === "true";
  const initialTokenExpiresAt: number | null = null;

  // Keep this hook around for backward compat with anything that still subscribes,
  // but we never actually mint new access tokens client-side any more.
  api.setOnTokensChanged((accessToken) => {
    const exp = getTokenExpiration(accessToken);
    set({ tokenExpiresAt: exp });
  });

  // On store creation (page load / new tab), if a soas_session cookie may still be alive
  // server-side, fetch the HMAC session key into memory so subsequent requests can sign.
  // The cookie itself is httpOnly so we can't read it from JS — we just try bootstrap and
  // accept silent failure (the router will then redirect to /login).
  // Defer with a microtask so the store factory has returned before we touch `get()`,
  // and always clear `isBootstrapping` once we know one way or the other.
  Promise.resolve().then(async () => {
    try {
      await get().bootstrapAppSession();
    } catch {
      // bootstrap swallows its own errors; this is just a safety net.
    } finally {
      set({ isBootstrapping: false });
    }
  });

  return {
    user: initialUser,
    isAuthenticated: initialUser !== null,
    isBootstrapping: true,
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

        const { must_reset_password } = res as { must_reset_password?: boolean };
        // Login already set the soas_session cookie. Pull the HMAC key + user identity
        // from /auth/session/bootstrap — this is the only post-login state we need.
        await get().bootstrapAppSession();

        const mustReset = must_reset_password === true;
        if (mustReset) {
          localStorage.setItem("must_reset_password", "true");
          set({ mustResetPassword: true });
        } else {
          localStorage.removeItem("must_reset_password");
          set({ mustResetPassword: false });
        }

        return { must_reset_password: mustReset };
      } finally {
        set({ isLoading: false });
      }
    },

    verifyMfa: async (mfaToken, totpCode) => {
      set({ isLoading: true });
      try {
        const res = await api.post<{ must_reset_password?: boolean }>(
          "/auth/mfa/verify",
          { mfa_token: mfaToken, totp_code: totpCode }
        );
        // MFA endpoint also set the soas_session cookie. Bootstrap pulls the key + user.
        await get().bootstrapAppSession();

        const mustReset = res.must_reset_password === true;
        if (mustReset) {
          localStorage.setItem("must_reset_password", "true");
          set({ mustResetPassword: true });
        } else {
          localStorage.removeItem("must_reset_password");
          set({ mustResetPassword: false });
        }

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

    bootstrapAppSession: async () => {
      // Call /auth/session/bootstrap directly (not via the HMAC-signed api client) since
      // we are precisely fetching the signing key. The endpoint also returns user
      // identity so we don't need a second hop.
      try {
        const res = await fetch("/api/v1/auth/session/bootstrap", {
          method: "GET",
          credentials: "include",
        });
        if (!res.ok) return false;
        const data = await res.json();
        // Install the key inside the api client.
        await api.bootstrapSession();
        const me = data.user || {};
        const expiresAt = data.expires_at ? Math.floor(new Date(data.expires_at).getTime() / 1000) : null;
        set({
          user: {
            id: me.id,
            username: me.username,
            display_name: me.display_name || me.username,
            email: me.email || "",
            roles: me.roles || [],
            permissions: me.permissions || [],
            teams: me.teams || [],
          },
          isAuthenticated: true,
          tokenExpiresAt: expiresAt,
        });
        return true;
      } catch {
        return false;
      }
    },

    refreshSession: async () => {
      // No more refresh-token flow. To pick up role/permission changes, just re-fetch
      // identity from /auth/session/bootstrap (the cookie is still valid). If the
      // cookie has expired, bootstrap will 401 and we log out.
      set({ isRefreshing: true });
      try {
        const ok = await get().bootstrapAppSession();
        if (!ok) get().logout();
      } finally {
        set({ isRefreshing: false });
      }
    },
  };
});
