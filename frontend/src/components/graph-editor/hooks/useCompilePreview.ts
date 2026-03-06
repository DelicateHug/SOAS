/**
 * Hook for requesting a compile preview (generated Python code).
 */

import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { useGraphEditorStore } from "../stores/graphEditorStore";
import { toBackendFormat } from "../utils/graphConversion";

interface NodeMapEntry {
  type: string;
  label: string;
  start_line: number;
  end_line: number;
}

interface CompilePreviewResponse {
  code: string;
  valid: boolean;
  errors: Array<{ message: string }>;
  node_map: Record<string, NodeMapEntry>;
}

export function useCompilePreview() {
  const {
    toVP2GraphData,
    setIsCompiling,
    setGeneratedCode,
    setCompilationWarnings,
    setNodeMap,
  } = useGraphEditorStore();

  const mutation = useToastMutation({
    loadingMessage: false,
    successMessage: false,
    mutationFn: async () => {
      setIsCompiling(true);
      const graphData = toVP2GraphData();
      const backendData = toBackendFormat(graphData);
      return api.post<CompilePreviewResponse>(
        "/graph-editor/compile-preview",
        { graph: backendData }
      );
    },
    onSuccess: (data) => {
      setGeneratedCode(data.code);
      setNodeMap(data.node_map || null);
      setCompilationWarnings(
        (data.errors || []).map((e) => ({
          message: e.message,
        }))
      );
      setIsCompiling(false);
    },
    onError: () => {
      setIsCompiling(false);
    },
  });

  return mutation;
}
