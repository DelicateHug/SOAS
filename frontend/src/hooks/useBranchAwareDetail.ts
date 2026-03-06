/**
 * Composes useEntityVersion + useEntityDraft + useDeploymentMode
 * for detail/edit pages that need branch awareness.
 */

import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import { useEntityVersion } from "@/hooks/useEntityVersion";
import { useEntityDraft } from "@/hooks/useEntityDraft";

export function useBranchAwareDetail(entityType: string, entityId: string | undefined) {
  const { isDevMode } = useDeploymentMode();
  const version = useEntityVersion(entityType, entityId ?? null, isDevMode && !!entityId);
  const { draft, hasDraft, refetch: refetchDraft } = useEntityDraft(entityType, entityId ?? null);

  return {
    ...version,
    draft,
    hasDraft,
    refetchDraft,
    isDevMode,
  };
}
