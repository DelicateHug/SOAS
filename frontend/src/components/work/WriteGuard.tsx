/**
 * Wraps mutating UI (forms, action buttons) so it greys out and stops
 * receiving clicks under two independent conditions:
 *
 *  1. No active work session for the current target (analyst time-tracking gate).
 *  2. (Optional) The current user does not hold a specific permission — used to
 *     hide Tier 2 controls from Tier 1 analysts and Tier 3 controls from Tiers 1-2.
 *
 * Read-only views must not be wrapped — visiting tabs and seeing data is always
 * allowed. Only wrap input rows / submit buttons / action toolbars.
 *
 * Server-side RBAC still enforces both rules; this is the UI half.
 */
import { type ReactNode } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useWorkGate } from "./WorkGateContext";

interface Props {
  children: ReactNode;
  /** Override hint shown on hover when blocked. */
  blockedTitle?: string;
  /**
   * Permission required to use this control, e.g. "case:update" or "automation:execute".
   * When set, Tier-1 users (who have only :read) see the control greyed out with a
   * tooltip explaining the tier requirement.
   */
  requiredPermission?: string;
}

export function WriteGuard({ children, blockedTitle, requiredPermission }: Props) {
  const { isWorking } = useWorkGate();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const allowedByTier = requiredPermission ? hasPermission(requiredPermission) : true;

  if (isWorking && allowedByTier) return <>{children}</>;

  const reason = !allowedByTier
    ? `Your role does not grant ${requiredPermission}`
    : (blockedTitle ?? "Start work on this item to edit");

  return (
    <div
      className="opacity-50 pointer-events-none select-none"
      aria-disabled="true"
      title={reason}
    >
      {children}
    </div>
  );
}
