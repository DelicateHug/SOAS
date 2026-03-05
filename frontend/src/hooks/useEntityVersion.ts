/**
 * Hook for fetching entity versions from the three-tier branching system.
 *
 * In dev mode: fetches the effective version (user draft > dev > prod).
 * Allows switching between tiers via setTier().
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { EntityVersionResponse, VersionTier } from "@/types/api";

export function useEntityVersion(
  entityType: string,
  entityId: string | null | undefined,
  enabled = true,
) {
  const [selectedTier, setSelectedTier] = useState<VersionTier | null>(null);

  // Fetch effective version (user > dev > prod)
  const effectiveQuery = useQuery<EntityVersionResponse>({
    queryKey: ["entity-version", entityType, entityId, "effective"],
    queryFn: () =>
      api.get<EntityVersionResponse>(
        `/branch-versions/entity/${entityType}/${entityId}`,
      ),
    enabled: enabled && !!entityId,
  });

  // Fetch specific tier version (only when user explicitly selects a tier)
  const tierQuery = useQuery<EntityVersionResponse>({
    queryKey: ["entity-version", entityType, entityId, selectedTier],
    queryFn: () =>
      api.get<EntityVersionResponse>(
        `/branch-versions/entity/${entityType}/${entityId}?tier=${selectedTier}`,
      ),
    enabled: enabled && !!entityId && !!selectedTier,
  });

  // Use tier-specific result if a tier is selected, otherwise use effective
  const activeQuery = selectedTier ? tierQuery : effectiveQuery;

  return {
    /** The entity snapshot at the current tier */
    snapshot: activeQuery.data?.snapshot ?? null,
    /** Which tier the snapshot came from */
    sourceTier: activeQuery.data?.tier ?? ("prod" as VersionTier),
    /** Whether a specific tier is manually selected */
    selectedTier,
    /** Switch to a specific tier, or null for effective */
    setTier: (tier: VersionTier | null) => setSelectedTier(tier),
    isLoading: activeQuery.isLoading,
    isError: activeQuery.isError,
  };
}
