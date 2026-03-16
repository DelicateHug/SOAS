/**
 * Guards edit actions in production mode.
 * Renders children only when NOT in production mode.
 * For git-synced entities only — issues are exempt.
 */

import type { ReactNode } from "react";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";

interface ProductionGuardProps {
  children: ReactNode;
  /** Optional fallback to show instead (e.g., a "view only" label) */
  fallback?: ReactNode;
}

export function ProductionGuard({ children, fallback = null }: ProductionGuardProps) {
  const { isProduction } = useDeploymentMode();
  if (isProduction) return <>{fallback}</>;
  return <>{children}</>;
}
