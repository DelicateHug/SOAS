/**
 * Webview override for useDeploymentMode.
 * Reads dev mode state from the webview API bridge, which receives
 * updates from the extension host via postMessage.
 */

import { useCallback, useSyncExternalStore } from "react";
import { api } from "@/lib/api";

// The webview api.ts manages devModeListeners internally.
// We tap into the same mechanism here by polling api.devMode.
// Since setDevMode in the webview's api.ts notifies devModeListeners,
// we subscribe via a window event for simplicity.
const listeners = new Set<() => void>();

// Listen for dev-mode-changed messages and notify subscribers
window.addEventListener("message", (event) => {
  if (event.data?.type === "dev-mode-changed") {
    listeners.forEach((l) => l());
  }
});

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return api.devMode;
}

export function useDeploymentMode() {
  const isDevMode = useSyncExternalStore(subscribe, getSnapshot);

  const toggleDevMode = useCallback(() => {
    // In the webview, toggling is done via the extension host status bar.
    // This is a no-op here.
  }, []);

  const setDevMode = useCallback((_enabled: boolean) => {
    // No-op: dev mode is controlled by the extension host
  }, []);

  return {
    isDevMode,
    isProduction: !isDevMode,
    canToggle: false, // Can't toggle from within webview
    toggleDevMode,
    setDevMode,
  };
}
