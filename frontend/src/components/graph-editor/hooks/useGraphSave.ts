/**
 * Hook for saving graph data as a draft change request.
 *
 * All saves go through the change request system. Only admin "Apply"
 * writes to the live automations table.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { useGraphEditorStore } from "../stores/graphEditorStore";
import { toBackendFormat } from "../utils/graphConversion";
import type { ChangeRequestCreate, ChangeRequestDetail } from "@/types/api";

export function useGraphSave(automationId: string | undefined) {
  const queryClient = useQueryClient();

  // Use getState() to avoid subscribing to the entire store —
  // subscribing without a selector causes GraphEditor to re-render
  // on every single state change (node drags, selections, etc.).
  const store = useGraphEditorStore;
  const setIsSaving = store((s) => s.setIsSaving);
  const setIsDirty = store((s) => s.setIsDirty);
  const toVP2GraphData = store((s) => s.toVP2GraphData);

  const mutation = useToastMutation({
    loadingMessage: false,
    successMessage: false,
    mutationFn: async () => {
      // Read graphId from store at mutation time — it may have been set after hook creation
      const id = automationId || useGraphEditorStore.getState().graphId;
      if (!id) throw new Error("No automation ID");

      setIsSaving(true);
      const graphData = toVP2GraphData();
      const backendData = toBackendFormat(graphData);

      const body: ChangeRequestCreate = {
        entity_type: "automation",
        entity_id: id,
        action: "update",
        title: "Update automation graph",
        snapshot: { graph_data: backendData },
      };
      return api.post<ChangeRequestDetail>("/change-requests", body);
    },
    onSuccess: () => {
      setIsDirty(false);
      setIsSaving(false);
      queryClient.invalidateQueries({ queryKey: ["change-request"] });
    },
    onError: () => {
      setIsSaving(false);
    },
  });

  return mutation;
}
