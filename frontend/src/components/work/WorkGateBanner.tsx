/**
 * Banner shown above tab content when the user can view but cannot edit because
 * they don't have an active work session on this target. Click-through to the
 * Overview tab where the Start work button lives in the sidebar.
 */
import { Clock, Lock } from "lucide-react";
import { useWorkGate } from "./WorkGateContext";

export function WorkGateBanner() {
  const { isWorking, workingOnOther, isLoading } = useWorkGate();
  if (isLoading || isWorking) return null;

  return (
    <div className="mb-3 flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-[var(--color-text)]">
      <Lock size={14} className="text-amber-600 dark:text-amber-400 shrink-0" />
      <div className="flex-1">
        <span className="font-medium">Read-only</span>
        <span className="text-[var(--color-text-muted)]">
          {" — "}
          {workingOnOther
            ? "You have an active work session on another item. Start work here to edit (it will pause the other)."
            : "Click Start work in the sidebar to claim and edit this item."}
        </span>
      </div>
      <Clock size={12} className="text-amber-600 dark:text-amber-400 shrink-0" />
    </div>
  );
}
