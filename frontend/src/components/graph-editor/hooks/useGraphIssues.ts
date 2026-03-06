import { useState, useCallback, useRef, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import type { GraphIssueItem, GraphAnnotation } from "@/types/api";

const CLOSED_STATUSES = new Set(["closed", "resolved", "wont_fix"]);

export function useGraphIssues(automationId: string | undefined, onAnnotationSaved?: () => void) {
  const [showIssues, setShowIssues] = useState(true);
  const queryClient = useQueryClient();

  // Track issue IDs that were already closed when the page loaded.
  // These get filtered out; issues closed during the session stay visible
  // until the user navigates away (ref resets on unmount).
  const initiallyClosedRef = useRef<Set<string> | null>(null);

  const { data } = useQuery({
    queryKey: ["automation-graph-issues", automationId],
    queryFn: () =>
      api.get<GraphIssueItem[]>(`/issues/automation-graph/${automationId}`),
    enabled: !!automationId && showIssues,
  });

  // On first successful fetch, snapshot which issues are already closed
  if (data && initiallyClosedRef.current === null) {
    initiallyClosedRef.current = new Set(
      data.filter((i) => CLOSED_STATUSES.has(i.status)).map((i) => i.id)
    );
  }

  // Hide issues that were already closed on page load
  const visibleIssues = useMemo(() => {
    if (!data) return [];
    const initial = initiallyClosedRef.current;
    if (!initial || initial.size === 0) return data;
    return data.filter((i) => !initial.has(i.id));
  }, [data]);

  const updateAnnotation = useToastMutation({
    loadingMessage: false,
    successMessage: false,
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
    onSuccess: () => {
      onAnnotationSaved?.();
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
    issues: visibleIssues,
    showIssues,
    setShowIssues,
    saveAnnotation,
  };
}
