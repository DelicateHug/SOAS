/**
 * Hook to fetch the active draft/submitted change request for a specific entity.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ChangeRequestDetail } from "@/types/api";

export function useEntityDraft(entityType: string, entityId: string | null | undefined) {
  const query = useQuery<ChangeRequestDetail | null>({
    queryKey: ["change-request", "entity", entityType, entityId],
    queryFn: async () => {
      if (!entityId) return null;
      return api.get<ChangeRequestDetail | null>(
        `/change-requests/entity/${entityType}/${entityId}`
      );
    },
    enabled: !!entityId,
  });

  return {
    draft: query.data ?? null,
    hasDraft: !!query.data,
    isLoading: query.isLoading,
    refetch: query.refetch,
  };
}
