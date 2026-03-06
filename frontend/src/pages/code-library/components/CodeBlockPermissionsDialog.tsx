/**
 * Permissions dialog for code library blocks.
 * Controls which roles can read, edit, or use (add to graph) a code block.
 */

import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { Shield, Loader2, X } from "lucide-react";

interface Role {
  id: string;
  name: string;
  display_name: string;
}

interface CodeBlockPermission {
  block_id: string;
  role_id: string;
  role_name: string;
  role_display_name: string;
  can_read: boolean;
  can_edit: boolean;
  can_use: boolean;
}

interface CodeBlockPermissionsDialogProps {
  blockId: string;
  blockName: string;
  onClose: () => void;
}

export function CodeBlockPermissionsDialog({
  blockId,
  blockName,
  onClose,
}: CodeBlockPermissionsDialogProps) {
  const queryClient = useQueryClient();

  const { data: rolesData } = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<{ data: Role[] }>("/roles"),
  });

  const { data: permissions, isLoading: isLoadingPerms } = useQuery({
    queryKey: ["code-block-permissions", blockId],
    queryFn: () =>
      api.get<CodeBlockPermission[]>(`/code-library/${blockId}/permissions`),
    enabled: !!blockId,
  });

  const [localPerms, setLocalPerms] = useState<
    Map<string, { can_read: boolean; can_edit: boolean; can_use: boolean }>
  >(new Map());
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (permissions) {
      const map = new Map<
        string,
        { can_read: boolean; can_edit: boolean; can_use: boolean }
      >();
      for (const p of permissions) {
        map.set(p.role_id, {
          can_read: p.can_read,
          can_edit: p.can_edit,
          can_use: p.can_use,
        });
      }
      setLocalPerms(map);
      setIsDirty(false);
    }
  }, [permissions]);

  const roles =
    rolesData?.data ||
    (Array.isArray(rolesData) ? (rolesData as unknown as Role[]) : []);

  const togglePermission = useCallback(
    (roleId: string, field: "can_read" | "can_edit" | "can_use") => {
      setLocalPerms((prev) => {
        const next = new Map(prev);
        const existing = next.get(roleId) || {
          can_read: false,
          can_edit: false,
          can_use: false,
        };
        next.set(roleId, { ...existing, [field]: !existing[field] });
        return next;
      });
      setIsDirty(true);
    },
    []
  );

  const saveMutation = useToastMutation({
    mutationFn: async () => {
      const body = Array.from(localPerms.entries())
        .filter(([, v]) => v.can_read || v.can_edit || v.can_use)
        .map(([roleId, v]) => ({
          role_id: roleId,
          can_read: v.can_read,
          can_edit: v.can_edit,
          can_use: v.can_use,
        }));

      return api.request(`/code-library/${blockId}/permissions`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
    },
    loadingMessage: "Saving permissions...",
    successMessage: "Permissions saved.",
    onSuccess: () => {
      setIsDirty(false);
      queryClient.invalidateQueries({
        queryKey: ["code-block-permissions", blockId],
      });
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--background))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[560px] max-h-[70vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4" />
            <h2 className="text-sm font-semibold">Block Permissions</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[hsl(var(--accent))] rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Description */}
        <div className="px-4 py-2 text-xs text-[hsl(var(--muted-foreground))] border-b border-[hsl(var(--border))]">
          Control which roles can read, edit, or use &ldquo;{blockName}&rdquo;
          in their graphs.
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {isLoadingPerms ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-[hsl(var(--muted-foreground))]" />
            </div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[hsl(var(--muted-foreground))]">
                  <th className="pb-2 font-medium">Role</th>
                  <th className="pb-2 font-medium text-center w-16">Read</th>
                  <th className="pb-2 font-medium text-center w-16">Edit</th>
                  <th className="pb-2 font-medium text-center w-16">Use</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => {
                  const perms = localPerms.get(role.id) || {
                    can_read: false,
                    can_edit: false,
                    can_use: false,
                  };
                  return (
                    <tr
                      key={role.id}
                      className="border-t border-[hsl(var(--border))]"
                    >
                      <td className="py-2">
                        <div>
                          <span className="font-medium">
                            {role.display_name}
                          </span>
                          <span className="text-[hsl(var(--muted-foreground))] ml-1.5">
                            ({role.name})
                          </span>
                        </div>
                      </td>
                      <td className="py-2 text-center">
                        <input
                          type="checkbox"
                          checked={perms.can_read}
                          onChange={() =>
                            togglePermission(role.id, "can_read")
                          }
                          className="rounded border-[hsl(var(--input))]"
                        />
                      </td>
                      <td className="py-2 text-center">
                        <input
                          type="checkbox"
                          checked={perms.can_edit}
                          onChange={() =>
                            togglePermission(role.id, "can_edit")
                          }
                          className="rounded border-[hsl(var(--input))]"
                        />
                      </td>
                      <td className="py-2 text-center">
                        <input
                          type="checkbox"
                          checked={perms.can_use}
                          onChange={() =>
                            togglePermission(role.id, "can_use")
                          }
                          className="rounded border-[hsl(var(--input))]"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[hsl(var(--border))]">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!isDirty || saveMutation.isPending}
            className="px-3 py-1.5 text-xs rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
          >
            {saveMutation.isPending ? (
              <Loader2 className="w-3 h-3 animate-spin inline mr-1" />
            ) : null}
            Save Permissions
          </button>
        </div>
      </div>
    </div>
  );
}
