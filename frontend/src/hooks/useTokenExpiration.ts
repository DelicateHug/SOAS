import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";

export type UrgencyLevel = "ok" | "warning" | "critical" | "expired";

interface TokenExpirationInfo {
  remainingText: string;
  remainingSeconds: number;
  urgency: UrgencyLevel;
}

export function useTokenExpiration(): TokenExpirationInfo {
  const tokenExpiresAt = useAuthStore((s) => s.tokenExpiresAt);
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    if (tokenExpiresAt === null) return;

    const tick = () => {
      const currentNow = Math.floor(Date.now() / 1000);
      setNow(currentNow);
      const remaining = tokenExpiresAt - currentNow;
      // Always tick every second so the displayed seconds count down smoothly
      const delay = remaining <= 0 ? 5000 : 1000;
      timer = setTimeout(tick, delay);
    };

    let timer = setTimeout(tick, 0);

    // Pause when tab is hidden, catch up when visible
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        setNow(Math.floor(Date.now() / 1000));
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [tokenExpiresAt]);

  if (tokenExpiresAt === null) {
    return { remainingText: "--", remainingSeconds: 0, urgency: "ok" };
  }

  const remaining = tokenExpiresAt - now;

  let urgency: UrgencyLevel;
  if (remaining <= 0) {
    urgency = "expired";
  } else if (remaining < 120) {
    urgency = "critical";
  } else if (remaining < 600) {
    urgency = "warning";
  } else {
    urgency = "ok";
  }

  let remainingText: string;
  if (remaining <= 0) {
    remainingText = "Expired";
  } else if (remaining >= 60) {
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    remainingText = seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
  } else {
    remainingText = `${remaining}s`;
  }

  return { remainingText, remainingSeconds: remaining, urgency };
}
