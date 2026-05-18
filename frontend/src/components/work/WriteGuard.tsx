/**
 * Wraps mutating UI (forms, action buttons) so it greys out and stops
 * receiving clicks when the user doesn't have an active work session.
 *
 * Read-only views must not be wrapped — visiting tabs and seeing data is
 * always allowed. Only wrap input rows / submit buttons / action toolbars.
 *
 * Server-side RBAC still enforces the rule; this is the UI half.
 */
import { type ReactNode } from "react";
import { useWorkGate } from "./WorkGateContext";

interface Props {
  children: ReactNode;
  /** Override hint shown on hover when blocked. */
  blockedTitle?: string;
}

export function WriteGuard({ children, blockedTitle }: Props) {
  const { isWorking } = useWorkGate();
  if (isWorking) return <>{children}</>;
  return (
    <div
      className="opacity-50 pointer-events-none select-none"
      aria-disabled="true"
      title={blockedTitle ?? "Start work on this item to edit"}
    >
      {children}
    </div>
  );
}
