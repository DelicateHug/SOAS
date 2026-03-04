/**
 * Hook for saving graph data to the backend.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useGraphEditorStore } from "../stores/graphEditorStore";
import { toBackendFormat } from "../utils/graphConversion";

export function useGraphSave(automationId: string | undefined) {
  const queryClient = useQueryClient();
  const { setIsSaving, setIsDirty, toVP2GraphData } = useGraphEditorStore();

  const mutation = useMutation({
    mutationFn: async () => {
      // Read graphId from store at mutation time — it may have been set after hook creation
      const id = automationId || useGraphEditorStore.getState().graphId;
      if (!id) throw new Error("No automation ID");

      setIsSaving(true);
      const graphData = toVP2GraphData();
      const backendData = toBackendFormat(graphData);

      return api.request<{ id: string }>(`/automations/${id}/graph`, {
        method: "PUT",
        body: JSON.stringify({ graph_data: backendData }),
      });
    },
    onSuccess: () => {
      setIsDirty(false);
      setIsSaving(false);
      const id = automationId || useGraphEditorStore.getState().graphId;
      if (id) {
        queryClient.invalidateQueries({ queryKey: ["automation", id] });
      }
    },
    onError: () => {
      setIsSaving(false);
    },
  });

  return mutation;
}
