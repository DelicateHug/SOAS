/**
 * Reusable version management component for automations, code blocks, and jobs.
 * Shows a dropdown panel for listing, creating, editing, and restoring versions.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { History, Plus, RotateCcw, Check, X, Pencil, Loader2, ChevronDown } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Version {
  id: string;
  version_number: number;
  name: string | null;
  description: string | null;
  created_by: { id: string; username: string; display_name: string };
  created_at: string;
}

interface VersionManagerProps {
  entityType: "automation" | "code-library" | "job";
  entityId: string;
  currentVersion: number;
  onVersionRestored?: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build the base API path segment for the given entity type + id. */
function basePath(entityType: VersionManagerProps["entityType"], entityId: string): string {
  switch (entityType) {
    case "automation":
      return `/automations/${entityId}`;
    case "code-library":
      return `/code-library/${entityId}`;
    case "job":
      return `/jobs/${entityId}`;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Inline form for creating a new version. */
function CreateVersionForm({
  onSubmit,
  onCancel,
  isPending,
}: {
  onSubmit: (name: string, description: string) => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit(name.trim(), description.trim());
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-3 border-b border-[var(--color-border)] bg-[var(--color-surface-2)]/30"
    >
      <label className="block text-[11px] font-medium text-[var(--color-text-muted)] mb-1">
        Version name <span className="text-red-400">*</span>
      </label>
      <input
        ref={nameRef}
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. v6 – added email alert"
        className="w-full px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-primary)] mb-2"
      />
      <label className="block text-[11px] font-medium text-[var(--color-text-muted)] mb-1">
        Description
      </label>
      <input
        type="text"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Optional description"
        className="w-full px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-primary)] mb-2"
      />
      <div className="flex items-center justify-end gap-1.5">
        <button
          type="button"
          onClick={onCancel}
          disabled={isPending}
          className="px-2 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!name.trim() || isPending}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50 transition-colors"
        >
          {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
          Create
        </button>
      </div>
    </form>
  );
}

/** Confirmation dialog for restoring a version. */
function RestoreConfirmDialog({
  versionNumber,
  onConfirm,
  onCancel,
  isPending,
}: {
  versionNumber: number;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl w-[380px] p-4">
        <h3 className="text-sm font-semibold mb-2">Restore to version {versionNumber}?</h3>
        <p className="text-xs text-[var(--color-text-muted)] mb-4">
          This will overwrite the current state. You may want to create a new version
          of the current state first.
        </p>
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={isPending}
            className="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            {isPending && <Loader2 className="w-3 h-3 animate-spin" />}
            Restore
          </button>
        </div>
      </div>
    </div>
  );
}

/** A single version row with inline-edit support. */
function VersionRow({
  version,
  isCurrent,
  onRestore,
  onUpdate,
  isUpdating,
}: {
  version: Version;
  isCurrent: boolean;
  onRestore: (versionNumber: number) => void;
  onUpdate: (versionNumber: number, name: string, description: string) => void;
  isUpdating: boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(version.name ?? "");
  const [editDesc, setEditDesc] = useState(version.description ?? "");
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing) {
      nameInputRef.current?.focus();
      nameInputRef.current?.select();
    }
  }, [isEditing]);

  const startEditing = () => {
    setEditName(version.name ?? "");
    setEditDesc(version.description ?? "");
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  const saveEdit = () => {
    onUpdate(version.version_number, editName.trim(), editDesc.trim());
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      saveEdit();
    } else if (e.key === "Escape") {
      cancelEditing();
    }
  };

  return (
    <div
      className={`group px-3 py-2 border-b border-[var(--color-border)] last:border-b-0 transition-colors ${
        isCurrent
          ? "bg-[var(--color-primary)]/8 border-l-2 border-l-[var(--color-primary)]"
          : "hover:bg-[var(--color-surface-2)]/50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Left side: version info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span
              className={`text-xs font-semibold ${
                isCurrent ? "text-[var(--color-primary)]" : "text-[var(--color-text)]"
              }`}
            >
              v{version.version_number}
            </span>
            {isCurrent && (
              <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--color-primary)]/15 text-[var(--color-primary)] font-medium">
                current
              </span>
            )}
          </div>

          {isEditing ? (
            <div className="mt-1 space-y-1">
              <input
                ref={nameInputRef}
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Version name"
                className="w-full px-1.5 py-0.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-primary)]"
              />
              <input
                type="text"
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Description (optional)"
                className="w-full px-1.5 py-0.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-primary)]"
              />
              <div className="flex items-center gap-1">
                <button
                  onClick={saveEdit}
                  disabled={isUpdating}
                  className="p-0.5 rounded hover:bg-[var(--color-surface-2)] text-green-500"
                  title="Save"
                >
                  {isUpdating ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Check className="w-3 h-3" />
                  )}
                </button>
                <button
                  onClick={cancelEditing}
                  className="p-0.5 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
                  title="Cancel"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            </div>
          ) : (
            <>
              {version.name && (
                <p className="text-xs text-[var(--color-text)] mt-0.5 truncate">{version.name}</p>
              )}
              {version.description && (
                <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5 truncate max-w-[220px]">
                  {version.description}
                </p>
              )}
              <div className="flex items-center gap-1.5 mt-1 text-[10px] text-[var(--color-text-muted)]">
                <span>{version.created_by.display_name}</span>
                <span>&middot;</span>
                <span>{formatDate(version.created_at)}</span>
              </div>
            </>
          )}
        </div>

        {/* Right side: action buttons (hidden during edit) */}
        {!isEditing && (
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button
              onClick={startEditing}
              className="p-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              title="Edit name/description"
            >
              <Pencil className="w-3 h-3" />
            </button>
            {!isCurrent && (
              <button
                onClick={() => onRestore(version.version_number)}
                className="p-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                title={`Restore to v${version.version_number}`}
              >
                <RotateCcw className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function VersionManager({
  entityType,
  entityId,
  currentVersion,
  onVersionRestored,
}: VersionManagerProps) {
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState<number | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0 });

  const apiBase = basePath(entityType, entityId);
  const queryKey = ["versions", entityType, entityId];

  // -----------------------------------------------------------------------
  // Position the portal-rendered dropdown relative to the trigger button
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen || !triggerRef.current) return;

    function updatePosition() {
      const rect = triggerRef.current!.getBoundingClientRect();
      const panelWidth = 320; // w-80
      // Anchor left edge to button's left; if it overflows right, shift left
      let left = rect.left;
      if (left + panelWidth > window.innerWidth - 8) {
        left = window.innerWidth - panelWidth - 8;
      }
      setPanelPos({
        top: rect.bottom + 4,
        left,
      });
    }

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [isOpen]);

  // -----------------------------------------------------------------------
  // Click-outside handling
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (
        triggerRef.current?.contains(target) ||
        panelRef.current?.contains(target)
      ) {
        return;
      }
      setIsOpen(false);
      setShowCreateForm(false);
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  // -----------------------------------------------------------------------
  // Queries
  // -----------------------------------------------------------------------
  const {
    data: versions,
    isLoading,
  } = useQuery({
    queryKey,
    queryFn: () => api.get<Version[]>(`${apiBase}/versions`),
    enabled: isOpen,
  });

  // -----------------------------------------------------------------------
  // Mutations
  // -----------------------------------------------------------------------
  const createMutation = useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      api.post<Version>(`${apiBase}/versions`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      setShowCreateForm(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      versionNumber,
      name,
      description,
    }: {
      versionNumber: number;
      name: string;
      description: string;
    }) =>
      api.patch<Version>(`${apiBase}/versions/${versionNumber}`, {
        name: name || null,
        description: description || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (versionNumber: number) =>
      api.post(`${apiBase}/versions/${versionNumber}/restore`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
      setRestoreTarget(null);
      setIsOpen(false);
      onVersionRestored?.();
    },
  });

  // -----------------------------------------------------------------------
  // Handlers
  // -----------------------------------------------------------------------
  const handleCreate = useCallback(
    (name: string, description: string) => {
      createMutation.mutate({
        name,
        description: description || undefined,
      });
    },
    [createMutation],
  );

  const handleUpdate = useCallback(
    (versionNumber: number, name: string, description: string) => {
      updateMutation.mutate({ versionNumber, name, description });
    },
    [updateMutation],
  );

  const togglePanel = () => {
    setIsOpen((prev) => !prev);
    if (isOpen) {
      setShowCreateForm(false);
    }
  };

  // Sort versions newest first
  const sortedVersions = versions
    ? [...versions].sort((a, b) => b.version_number - a.version_number)
    : [];

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <>
      {/* Trigger button */}
      <button
        ref={triggerRef}
        onClick={togglePanel}
        className={`flex items-center gap-1 px-2 py-1.5 text-xs rounded border transition-colors ${
          isOpen
            ? "border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/8"
            : "border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
        }`}
        title="Manage versions"
      >
        <History className="w-3.5 h-3.5" />
        <span className="font-medium">v{currentVersion}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown panel – rendered via portal so it escapes overflow containers */}
      {isOpen &&
        createPortal(
          <div
            ref={panelRef}
            className="fixed w-80 z-[9999] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] shadow-xl overflow-hidden"
            style={{ top: panelPos.top, left: panelPos.left }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)]">
              <span className="text-xs font-semibold text-[var(--color-text)]">Versions</span>
              {!showCreateForm && (
                <button
                  onClick={() => setShowCreateForm(true)}
                  className="flex items-center gap-1 px-2 py-1 text-[11px] rounded bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 transition-colors"
                >
                  <Plus className="w-3 h-3" />
                  New Version
                </button>
              )}
            </div>

            {/* Create form */}
            {showCreateForm && (
              <CreateVersionForm
                onSubmit={handleCreate}
                onCancel={() => setShowCreateForm(false)}
                isPending={createMutation.isPending}
              />
            )}

            {/* Version list */}
            <div className="max-h-96 overflow-y-auto">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-4 h-4 animate-spin text-[var(--color-text-muted)]" />
                </div>
              ) : sortedVersions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-[var(--color-text-muted)]">
                  <History className="w-5 h-5 mb-2 opacity-40" />
                  <p className="text-xs">No versions yet</p>
                  <p className="text-[11px] mt-0.5">
                    Create one to save the current state.
                  </p>
                </div>
              ) : (
                sortedVersions.map((version) => (
                  <VersionRow
                    key={version.id}
                    version={version}
                    isCurrent={version.version_number === currentVersion}
                    onRestore={setRestoreTarget}
                    onUpdate={handleUpdate}
                    isUpdating={updateMutation.isPending}
                  />
                ))
              )}
            </div>
          </div>,
          document.body,
        )}

      {/* Restore confirmation dialog */}
      {restoreTarget !== null && (
        <RestoreConfirmDialog
          versionNumber={restoreTarget}
          onConfirm={() => restoreMutation.mutate(restoreTarget)}
          onCancel={() => setRestoreTarget(null)}
          isPending={restoreMutation.isPending}
        />
      )}
    </>
  );
}
