/**
 * Frontend heartbeat: posts to /agents/heartbeat from the browser so an
 * active SOAS tab shows up in the Agents tab. One id per tab is not
 * useful (would flood the registry); instead we use a stable id derived
 * from a long-lived random localStorage value — multiple tabs from the
 * same user collapse to the same agenttype_id.
 *
 * Heartbeat fires while the document is visible. Stops while hidden so
 * minimised tabs don't keep agents looking alive forever.
 */
import { useEffect } from "react";

const STORAGE_KEY = "soasFrontendInstanceId";
const HEARTBEAT_MS = 30_000;

function resolveFrontendId(): string {
  try {
    let id = window.localStorage.getItem(STORAGE_KEY);
    if (!id || !/^frontend_[0-9]{3,}$/.test(id)) {
      // Random 3-digit suffix; collisions are fine, registry coalesces.
      const n = String(Math.floor(Math.random() * 900) + 100);
      id = `frontend_${n}`;
      window.localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return "frontend_001";
  }
}

export function useAgentHeartbeat(version: string = "0.1.0") {
  useEffect(() => {
    const agenttype_id = resolveFrontendId();
    const bootTs = Date.now();
    let cancelled = false;

    async function tick() {
      if (cancelled || document.visibilityState !== "visible") return;
      const body = {
        agenttype_id,
        role: "frontend",
        version,
        uptime_seconds: Math.floor((Date.now() - bootTs) / 1000),
        instance_id: agenttype_id,
      };
      try {
        await fetch("/api/v1/agents/heartbeat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          // Don't fight the rest of the app if backend is slow
          keepalive: true,
        });
      } catch {
        /* swallow */
      }
    }

    // First tick after a small delay so we don't race the login flow.
    const initial = window.setTimeout(tick, 5_000);
    const handle = window.setInterval(tick, HEARTBEAT_MS);
    const onVis = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      cancelled = true;
      window.clearTimeout(initial);
      window.clearInterval(handle);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [version]);
}
