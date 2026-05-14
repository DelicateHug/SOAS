/**
 * Button that starts/pauses/resumes/stops work on a given target.
 *
 * Variants:
 *   - target idle: shows "Start work" (green)
 *   - target is active session: shows "Stop work" (red) + live timer
 *   - target is paused session: shows "Resume" (primary)
 *   - other target is active: shows "Start work" but will auto-pause the other
 */
import { useEffect, useState } from "react";
import { Play, Pause, Square, Clock } from "lucide-react";
import { useWorkSession } from "@/hooks/useWorkSession";
import { cn } from "@/lib/utils";

interface Props {
  incidentId?: string;
  caseId?: string;
  size?: "sm" | "md";
}

export function StartWorkButton({ incidentId, caseId, size = "md" }: Props) {
  const { current, start, stop, pause, resume } = useWorkSession();

  const targetIsCurrent =
    current &&
    ((incidentId && current.incident_id === incidentId) ||
      (caseId && current.case_id === caseId));

  const isActive = targetIsCurrent && current?.status === "active";
  const isPaused = targetIsCurrent && current?.status === "paused";

  const baseCls = cn(
    "inline-flex items-center gap-1.5 rounded font-medium transition-colors disabled:opacity-50",
    size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-1.5 text-sm",
  );

  if (isActive) {
    return (
      <div className="inline-flex items-center gap-2">
        <LiveTimer baseSeconds={current!.live_seconds} />
        <button
          className={cn(baseCls, "border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]")}
          onClick={() => pause.mutate(current!.id)}
          disabled={pause.isPending}
          title="Pause work"
        >
          <Pause size={size === "sm" ? 11 : 13} /> Pause
        </button>
        <button
          className={cn(baseCls, "bg-[var(--color-danger)] text-white hover:opacity-90")}
          onClick={() => stop.mutate(current!.id)}
          disabled={stop.isPending}
        >
          <Square size={size === "sm" ? 11 : 13} /> Stop work
        </button>
      </div>
    );
  }

  if (isPaused) {
    return (
      <div className="inline-flex items-center gap-2">
        <span className="text-xs font-mono text-[var(--color-text-muted)]">
          paused @ {formatDuration(current!.accumulated_seconds)}
        </span>
        <button
          className={cn(baseCls, "bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]")}
          onClick={() => resume.mutate(current!.id)}
          disabled={resume.isPending}
        >
          <Play size={size === "sm" ? 11 : 13} /> Resume
        </button>
        <button
          className={cn(baseCls, "border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]")}
          onClick={() => stop.mutate(current!.id)}
          disabled={stop.isPending}
        >
          <Square size={size === "sm" ? 11 : 13} /> Stop
        </button>
      </div>
    );
  }

  const otherActive = current && current.status === "active";

  return (
    <button
      className={cn(
        baseCls,
        "bg-[var(--color-success)] text-white hover:opacity-90",
      )}
      onClick={() => start.mutate({ incident_id: incidentId, case_id: caseId })}
      disabled={start.isPending}
      title={
        otherActive
          ? "Will auto-pause your current session on another item"
          : "Start tracking work on this item"
      }
    >
      <Play size={size === "sm" ? 11 : 13} /> Start work
    </button>
  );
}

function LiveTimer({ baseSeconds }: { baseSeconds: number }) {
  // Snapshot when the component received the value; tick locally.
  const [snapshot] = useState({ base: baseSeconds, at: Date.now() });
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const h = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(h);
  }, []);

  const elapsed = snapshot.base + Math.floor((now - snapshot.at) / 1000);
  return (
    <span className="inline-flex items-center gap-1 text-xs font-mono text-[var(--color-success)]">
      <Clock size={11} />
      {formatDuration(elapsed)}
    </span>
  );
}

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  return `${m}:${String(ss).padStart(2, "0")}`;
}
