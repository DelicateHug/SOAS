import { useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import type { PaginatedResponse, CaseItem } from "@/types/api";

interface AddToGroupPopoverProps {
  incidentId: string;
  currentGroupIds: string[];
  onClose: () => void;
}

export function AddToGroupPopover({
  incidentId,
  currentGroupIds,
  onClose,
}: AddToGroupPopoverProps) {
  const queryClient = useQueryClient();
  const ref = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  const { data: groups, isLoading } = useQuery({
    queryKey: ["cases"],
    queryFn: () =>
      api.get<PaginatedResponse<CaseItem>>("/cases?per_page=100"),
  });

  const link = useMutation({
    mutationFn: (groupId: string) =>
      api.post(`/cases/${groupId}/incidents`, { incident_id: incidentId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["incident-groups"] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  const unlink = useMutation({
    mutationFn: (groupId: string) =>
      api.delete(`/cases/${groupId}/incidents/${incidentId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["incident-groups"] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  const toggleGroup = (groupId: string) => {
    if (currentGroupIds.includes(groupId)) {
      unlink.mutate(groupId);
    } else {
      link.mutate(groupId);
    }
  };

  return (
    <div
      ref={ref}
      className="absolute right-0 top-full mt-1 z-50 w-64 border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg"
    >
      <div className="px-3 py-2 border-b border-[hsl(var(--border))]">
        <p className="text-xs font-medium text-[hsl(var(--muted-foreground))]">
          Add to groups
        </p>
      </div>
      <div className="max-h-48 overflow-y-auto py-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-4 h-4 animate-spin text-[hsl(var(--muted-foreground))]" />
          </div>
        ) : !groups?.data.length ? (
          <p className="px-3 py-2 text-xs text-[hsl(var(--muted-foreground))]">
            No groups exist yet
          </p>
        ) : (
          groups.data.map((group) => {
            const isLinked = currentGroupIds.includes(group.id);
            return (
              <button
                key={group.id}
                onClick={() => toggleGroup(group.id)}
                disabled={link.isPending || unlink.isPending}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-[hsl(var(--accent))] disabled:opacity-50 text-left"
              >
                <input
                  type="checkbox"
                  checked={isLinked}
                  readOnly
                  className="rounded border-[hsl(var(--input))]"
                />
                <span className="flex-1 truncate">{group.title}</span>
                <span className="text-xs text-[hsl(var(--muted-foreground))]">
                  {group.status}
                </span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
