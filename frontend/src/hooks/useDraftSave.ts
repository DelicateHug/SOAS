/**
 * Hook that always saves through the change request / draft system.
 *
 * All user edits create draft change requests. Only admin "Apply"
 * writes to the live database.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  ChangeRequestCreate,
  ChangeRequestDetail,
  ChangeRequestAction,
} from "@/types/api";

interface DraftSaveOptions {
  entityType: string;
  entityId: string | null | undefined;
  /** Generate a human-readable title for the change request */
  getTitle: (snapshot: Record<string, unknown>) => string;
  /** Optional: compute a diff summary */
  getDiffSummary?: (
    snapshot: Record<string, unknown>
  ) => Record<string, { old: unknown; new: unknown }> | null;
}

export function useDraftSave({
  entityType,
  entityId,
  getTitle,
  getDiffSummary,
}: DraftSaveOptions) {
  const queryClient = useQueryClient();

  const draftMutation = useMutation<ChangeRequestDetail, unknown, Record<string, unknown>>({
    mutationFn: async (snapshot) => {
      const action: ChangeRequestAction = entityId ? "update" : "create";
      const body: ChangeRequestCreate = {
        entity_type: entityType,
        entity_id: entityId || null,
        action,
        title: getTitle(snapshot),
        snapshot,
        diff_summary: getDiffSummary?.(snapshot) ?? null,
      };
      return api.post<ChangeRequestDetail>("/change-requests", body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["change-requests"] });
    },
  });

  const submitMutation = useMutation<unknown, unknown, string>({
    mutationFn: (crId) => api.post(`/change-requests/${crId}/submit`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
      queryClient.invalidateQueries({ queryKey: ["change-requests"] });
    },
  });

  const save = async (snapshot: Record<string, unknown>): Promise<ChangeRequestDetail> => {
    return draftMutation.mutateAsync(snapshot);
  };

  return {
    save,
    isDraft: true,
    submitForReview: (crId: string) => submitMutation.mutateAsync(crId),
    lastDraft: draftMutation.data ?? null,
    isSaving: draftMutation.isPending,
    isSubmitting: submitMutation.isPending,
    error: draftMutation.error,
  };
}
