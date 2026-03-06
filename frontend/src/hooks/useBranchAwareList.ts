/**
 * Hook that enriches a list query with active change request overlay.
 *
 * In prod mode: zero overhead, just passes through the normal query.
 * In dev mode: fetches active CRs for the entity type and merges them
 * with the DB list to show pending creates/updates/deletes.
 */

import { useQuery, type QueryKey } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useDeploymentMode } from "@/hooks/useDeploymentMode";
import type { ChangeRequestDetail } from "@/types/api";

export type BranchStatus = "unchanged" | "modified" | "pending_delete";

export interface BranchAwareItem<T> {
  item: T;
  changeRequest?: ChangeRequestDetail;
  branchStatus: BranchStatus;
}

interface UseBranchAwareListOptions<T, R = { data: T[] }> {
  entityType: string;
  queryKey: QueryKey;
  queryFn: () => Promise<R>;
  getId: (item: T) => string;
  getData: (result: R) => T[];
  enabled?: boolean;
}

export function useBranchAwareList<T, R = { data: T[] }>({
  entityType,
  queryKey,
  queryFn,
  getId,
  getData,
  enabled = true,
}: UseBranchAwareListOptions<T, R>) {
  const { isDevMode } = useDeploymentMode();

  const mainQuery = useQuery<R>({
    queryKey,
    queryFn,
    enabled,
  });

  const crQuery = useQuery<ChangeRequestDetail[]>({
    queryKey: ["change-requests", "active", entityType],
    queryFn: () => api.get<ChangeRequestDetail[]>(`/change-requests/active?entity_type=${entityType}`),
    enabled: enabled && isDevMode,
    staleTime: 10_000,
  });

  const rawData = mainQuery.data ? getData(mainQuery.data) : [];
  const activeCRs = crQuery.data ?? [];

  // Build lookup: entity_id -> CR (for updates and deletes)
  const crByEntityId = new Map<string, ChangeRequestDetail>();
  const pendingCreates: ChangeRequestDetail[] = [];

  for (const cr of activeCRs) {
    if (cr.action === "create") {
      pendingCreates.push(cr);
    } else if (cr.entity_id) {
      // For update/delete, keep the most recent CR per entity
      if (!crByEntityId.has(cr.entity_id)) {
        crByEntityId.set(cr.entity_id, cr);
      }
    }
  }

  // Enrich DB items with CR metadata
  const items: BranchAwareItem<T>[] = rawData.map((item) => {
    const id = getId(item);
    const cr = crByEntityId.get(id);
    let branchStatus: BranchStatus = "unchanged";
    if (cr?.action === "delete") branchStatus = "pending_delete";
    else if (cr?.action === "update") branchStatus = "modified";
    return { item, changeRequest: cr, branchStatus };
  });

  return {
    items,
    pendingCreates: isDevMode ? pendingCreates : [],
    raw: mainQuery.data,
    isLoading: mainQuery.isLoading || (isDevMode && crQuery.isLoading),
    isDevMode,
    changeMap: crByEntityId,
  };
}
