/**
 * Top toolbar for the graph editor with save, validate, compile, test run,
 * undo/redo, and graph metadata inputs.
 */

import {
  Save,
  Undo2,
  Redo2,
  CheckCircle2,
  Code2,
  Play,
  RotateCw,
  Loader2,
  AlertTriangle,
  PanelLeft,
  PanelRight,
  Shield,
  Lock,
  LockOpen,
  Unlock,
  ListPlus,
  CircleDot,
} from "lucide-react";
import { useGraphEditorStore } from "./stores/graphEditorStore";
import { CollaboratorAvatars } from "./CollaboratorAvatars";
import type { Collaborator } from "./hooks/useCollaboration";

interface GraphEditorToolbarProps {
  onSave: () => void;
  onValidate: () => void;
  onCompile: () => void;
  onTestRun: () => void;
  onTestRunAgain: () => void;
  hasLastTestContext: boolean;
  onPermissions: () => void;
  onInputs: () => void;
  onShowErrors?: () => void;
  isTestRunStarting: boolean;
  isLeftPanelOpen: boolean;
  isRightPanelOpen: boolean;
  onToggleLeftPanel: () => void;
  onToggleRightPanel: () => void;
  // Collaboration props
  collaborators: Collaborator[];
  myUserId: string;
  isCollabConnected: boolean;
  isLockedByMe: boolean;
  isLockedByOther: boolean;
  lockHolderName?: string;
  onLockToggle: () => void;
  isReadOnly: boolean;
  /** True when in production mode — hides all write actions entirely */
  isProduction: boolean;
  // Issues overlay props
  showIssues: boolean;
  onToggleIssues: () => void;
  issueCount: number;
}

export function GraphEditorToolbar({
  onSave,
  onValidate,
  onCompile,
  onTestRun,
  onTestRunAgain,
  hasLastTestContext,
  onPermissions,
  onInputs,
  onShowErrors,
  isTestRunStarting,
  isLeftPanelOpen,
  isRightPanelOpen,
  onToggleLeftPanel,
  onToggleRightPanel,
  collaborators,
  myUserId,
  isCollabConnected,
  isLockedByMe,
  isLockedByOther,
  lockHolderName,
  onLockToggle,
  isReadOnly,
  isProduction,
  showIssues,
  onToggleIssues,
  issueCount,
}: GraphEditorToolbarProps) {
  const name = useGraphEditorStore((s) => s.name);
  const description = useGraphEditorStore((s) => s.description);
  const isDirty = useGraphEditorStore((s) => s.isDirty);
  const isSaving = useGraphEditorStore((s) => s.isSaving);
  const isCompiling = useGraphEditorStore((s) => s.isCompiling);
  const isTestRunning = useGraphEditorStore((s) => s.isTestRunning);
  const undoStack = useGraphEditorStore((s) => s.undoStack);
  const redoStack = useGraphEditorStore((s) => s.redoStack);
  const setName = useGraphEditorStore((s) => s.setName);
  const setDescription = useGraphEditorStore((s) => s.setDescription);
  const undo = useGraphEditorStore((s) => s.undo);
  const redo = useGraphEditorStore((s) => s.redo);
  const validationErrors = useGraphEditorStore((s) => s.validationErrors);

  return (
    <div className="h-10 border-b border-[hsl(var(--border))] bg-[hsl(var(--background))] flex items-center px-2 gap-1.5">
      {/* Panel toggles */}
      <button
        onClick={onToggleLeftPanel}
        className={`p-1.5 rounded hover:bg-[hsl(var(--accent))] transition-colors ${
          isLeftPanelOpen ? "text-[hsl(var(--foreground))]" : "text-[hsl(var(--muted-foreground))]"
        }`}
        title={isLeftPanelOpen ? "Hide node palette" : "Show node palette"}
      >
        <PanelLeft className="w-3.5 h-3.5" />
      </button>

      {/* Graph name */}
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        disabled={isReadOnly}
        className="px-2 py-1 text-xs font-medium border border-transparent hover:border-[hsl(var(--input))] focus:border-[hsl(var(--input))] rounded bg-transparent w-40 truncate disabled:opacity-50"
        placeholder="Graph name"
      />

      {/* Description (smaller) */}
      <input
        type="text"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        disabled={isReadOnly}
        className="px-2 py-1 text-[11px] border border-transparent hover:border-[hsl(var(--input))] focus:border-[hsl(var(--input))] rounded bg-transparent w-40 text-[hsl(var(--muted-foreground))] truncate disabled:opacity-50"
        placeholder="Description..."
      />

      {/* Save status (hidden in production) */}
      {!isProduction && (
        <div className="flex items-center gap-1 text-[11px] text-[hsl(var(--muted-foreground))] ml-1">
          {isSaving ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Saving...</span>
            </>
          ) : isDirty ? (
            <span className="text-yellow-600">Unsaved</span>
          ) : (
            <span className="text-green-600">Saved</span>
          )}
        </div>
      )}

      {/* Validation errors indicator */}
      {validationErrors.length > 0 && (
        <button
          onClick={onShowErrors}
          className="flex items-center gap-1 text-xs text-red-500 ml-1 hover:text-red-400 cursor-pointer"
          title="Click to view errors"
        >
          <AlertTriangle className="w-3 h-3" />
          {validationErrors.length} error{validationErrors.length !== 1 ? "s" : ""}
        </button>
      )}

      {/* Collaboration: avatars + connection status */}
      {isCollabConnected && (
        <>
          <div className="w-px h-5 bg-[hsl(var(--border))] mx-0.5" />
          <CollaboratorAvatars collaborators={collaborators} myUserId={myUserId} />
          <div className="flex items-center gap-1 text-[10px]">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
            <span className="text-[hsl(var(--muted-foreground))]">Live</span>
          </div>
        </>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Lock toggle (hidden in production) */}
      {!isProduction && isCollabConnected && (
        <button
          onClick={onLockToggle}
          disabled={isLockedByOther}
          className={`flex items-center gap-1 px-2 py-1.5 text-xs rounded transition-colors ${
            isLockedByMe
              ? "bg-amber-600 text-white hover:bg-amber-700"
              : isLockedByOther
                ? "text-amber-500 opacity-50 cursor-not-allowed"
                : "hover:bg-[hsl(var(--accent))]"
          }`}
          title={
            isLockedByMe
              ? "You have locked this graph. Click to unlock."
              : isLockedByOther
                ? `Locked by ${lockHolderName}`
                : "Lock graph for exclusive editing"
          }
        >
          {isLockedByOther ? (
            <Lock className="w-3.5 h-3.5" />
          ) : isLockedByMe ? (
            <Unlock className="w-3.5 h-3.5" />
          ) : (
            <LockOpen className="w-3.5 h-3.5" />
          )}
          {isLockedByMe ? "Unlock" : isLockedByOther ? "Locked" : "Lock"}
        </button>
      )}

      {!isProduction && (
        <>
          {/* Undo/Redo */}
          <button
            onClick={undo}
            disabled={undoStack.length === 0 || isReadOnly}
            className="p-1.5 rounded hover:bg-[hsl(var(--accent))] disabled:opacity-30 disabled:cursor-not-allowed"
            title="Undo (Ctrl+Z)"
          >
            <Undo2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={redo}
            disabled={redoStack.length === 0 || isReadOnly}
            className="p-1.5 rounded hover:bg-[hsl(var(--accent))] disabled:opacity-30 disabled:cursor-not-allowed"
            title="Redo (Ctrl+Y)"
          >
            <Redo2 className="w-3.5 h-3.5" />
          </button>

          {/* Divider */}
          <div className="w-px h-5 bg-[hsl(var(--border))] mx-0.5" />

          {/* Permissions */}
          <button
            onClick={onPermissions}
            className="flex items-center gap-1 px-2 py-1.5 text-xs rounded hover:bg-[hsl(var(--accent))] transition-colors"
            title="Manage execution permissions"
          >
            <Shield className="w-3.5 h-3.5" />
            Permissions
          </button>

          {/* Inputs */}
          <button
            onClick={onInputs}
            className="flex items-center gap-1 px-2 py-1.5 text-xs rounded hover:bg-[hsl(var(--accent))] transition-colors"
            title="Define automation inputs"
          >
            <ListPlus className="w-3.5 h-3.5" />
            Inputs
          </button>
        </>
      )}

      {/* Issues toggle */}
      <button
        onClick={onToggleIssues}
        className={`flex items-center gap-1 px-2 py-1.5 text-xs rounded transition-colors ${
          showIssues
            ? "bg-amber-600 text-white hover:bg-amber-700"
            : "hover:bg-[hsl(var(--accent))]"
        }`}
        title={showIssues ? "Hide issue annotations" : "Show issue annotations"}
      >
        <CircleDot className="w-3.5 h-3.5" />
        Issues
        {issueCount > 0 && (
          <span className={`text-[10px] rounded-full px-1.5 min-w-[18px] text-center ${
            showIssues ? "bg-white/20" : "bg-amber-500/20 text-amber-400"
          }`}>
            {issueCount}
          </span>
        )}
      </button>

      {!isProduction && (
        <>
          {/* Validate */}
          <button
            onClick={onValidate}
            className="flex items-center gap-1 px-2 py-1.5 text-xs rounded hover:bg-[hsl(var(--accent))] transition-colors"
            title="Validate graph"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Validate
          </button>

          {/* Compile Preview */}
          <button
            onClick={onCompile}
            disabled={isCompiling}
            className="flex items-center gap-1 px-2 py-1.5 text-xs rounded hover:bg-[hsl(var(--accent))] disabled:opacity-50 transition-colors"
            title="Preview generated code"
          >
            {isCompiling ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Code2 className="w-3.5 h-3.5" />
            )}
            Compile
          </button>

          {/* Test Run */}
          <button
            onClick={onTestRun}
            disabled={isTestRunning || isTestRunStarting || isReadOnly}
            className="flex items-center gap-1 px-2 py-1.5 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            title="Test run this graph"
          >
            {isTestRunning || isTestRunStarting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            Test Run
          </button>

          {/* Test Again - reuses previous test context */}
          {hasLastTestContext && (
            <button
              onClick={onTestRunAgain}
              disabled={isTestRunning || isTestRunStarting || isReadOnly}
              className="flex items-center gap-1 px-2 py-1.5 text-xs rounded bg-green-600/70 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
              title="Re-run test with previous context"
            >
              {isTestRunning || isTestRunStarting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RotateCw className="w-3.5 h-3.5" />
              )}
              Test Again
            </button>
          )}

          {/* Save */}
          <button
            onClick={onSave}
            disabled={!isDirty || isSaving || isReadOnly}
            className="flex items-center gap-1 px-2 py-1.5 text-xs rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50 transition-colors"
            title="Save graph (Ctrl+S)"
          >
            {isSaving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Save className="w-3.5 h-3.5" />
            )}
            Save
          </button>
        </>
      )}

      {/* Right panel toggle */}
      <button
        onClick={onToggleRightPanel}
        className={`p-1.5 rounded hover:bg-[hsl(var(--accent))] transition-colors ${
          isRightPanelOpen ? "text-[hsl(var(--foreground))]" : "text-[hsl(var(--muted-foreground))]"
        }`}
        title={isRightPanelOpen ? "Hide properties" : "Show properties"}
      >
        <PanelRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
