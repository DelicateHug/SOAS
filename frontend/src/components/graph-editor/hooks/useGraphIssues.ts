import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { GraphIssueItem, GraphAnnotation } from "@/types/api";

export function useGraphIssues(automationId: string | undefined) {
  const [showIssues, setShowIssues] = useState(true);
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ["automation-graph-issues", automationId],
    queryFn: () =>
      api.get<GraphIssueItem[]>(`/issues/automation-graph/${automationId}`),
    enabled: !!automationId && showIssues,
  });

  const updateAnnotation = useMutation({
    mutationFn: ({
      issueId,
      annotation,
    }: {
      issueId: string;
      annotation: GraphAnnotation;
    }) => api.patch(`/issues/${issueId}`, { graph_annotation: annotation }),
    onMutate: async ({ issueId, annotation }) => {
      const key = ["automation-graph-issues", automationId];
      await queryClient.cancelQueries({ queryKey: key });
      const prev = queryClient.getQueryData<GraphIssueItem[]>(key);
      queryClient.setQueryData<GraphIssueItem[]>(key, (old) =>
        old?.map((i) =>
          i.id === issueId ? { ...i, graph_annotation: annotation } : i
        )
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData(
          ["automation-graph-issues", automationId],
          ctx.prev
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ["automation-graph-issues", automationId],
      });
    },
  });

  const saveAnnotation = useCallback(
    (issueId: string, annotation: GraphAnnotation) => {
      updateAnnotation.mutate({ issueId, annotation });
    },
    [updateAnnotation]
  );

  return {
    issues: data ?? [],
    showIssues,
    setShowIssues,
    saveAnnotation,
  };
}
