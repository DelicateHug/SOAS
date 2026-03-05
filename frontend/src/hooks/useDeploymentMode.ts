/**
 * Per-user deployment mode toggle.
 *
 * Dev mode is opt-in: users with the 'deployment:dev_mode' permission can
 * toggle into development mode, which sends X-Dev-Mode: true with every API
 * request. Without it, all writes on protected paths are blocked (production).
 */

import { useCallback, useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

// Simple external store so all consumers re-render on toggle
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return api.devMode;
}

export function useDeploymentMode() {
  const { hasPermission } = useAuthStore();
  const isDevMode = useSyncExternalStore(subscribe, getSnapshot);

  const canToggle = hasPermission("deployment:dev_mode");

  const toggleDevMode = useCallback(() => {
    if (!canToggle) return;
    api.setDevMode(!api.devMode);
    // Notify all subscribers
    listeners.forEach((l) => l());
  }, [canToggle]);

  const setDevMode = useCallback(
    (enabled: boolean) => {
      if (!canToggle) return;
      api.setDevMode(enabled);
      listeners.forEach((l) => l());
    },
    [canToggle],
  );

  return {
    isDevMode,
    isProduction: !isDevMode,
    canToggle,
    toggleDevMode,
    setDevMode,
  };
}
