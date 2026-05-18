/**
 * Content-level gate. Wrap the inner tab content; when the user has no
 * active work session on this target, the children are hidden behind a
 * "Start work to view…" placeholder card.
 *
 * Mirrors case-mgmt's `<div class="work-gate">` pattern: read-only items
 * (history, chat, basic stats) should NOT be wrapped — they stay visible.
 * Only wrap the parts of a tab that would otherwise show sensitive case
 * detail behind the gate.
 */
import type { ReactNode } from "react";
import { Play, Lock } from "lucide-react";
import { useWorkGate } from "./WorkGateContext";

interface Props {
  children: ReactNode;
  /** Override copy for the placeholder. */
  title?: string;
  subtitle?: string;
}

export function WorkGateContent({ children, title, subtitle }: Props) {
  const { isWorking, workingOnOther, isLoading } = useWorkGate();

  if (isLoading || isWorking) return <>{children}</>;

  return (
    <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] px-6 py-12 text-center">
      <Lock className="mx-auto mb-3 text-[var(--color-text-muted)]" size={28} />
      <div className="text-sm font-semibold text-[var(--color-text)] flex items-center justify-center gap-1.5">
        <Play size={14} className="text-emerald-500" />
        {title ?? "Start work to view this content"}
      </div>
      <div className="mt-1.5 text-xs text-[var(--color-text-muted)] max-w-md mx-auto">
        {subtitle ??
          (workingOnOther
            ? "You have an active work session on another item. Start work here to view (it will pause the other)."
            : "Click Start work in the header to claim this item.")}
      </div>
    </div>
  );
}
