import { cn } from "@/lib/utils";

type Variant = "default" | "primary" | "success" | "warning" | "danger" | "info";

const VARIANT_CLASSES: Record<Variant, string> = {
  default: "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]",
  primary: "bg-[var(--color-status-investigating-bg)] text-[var(--color-status-investigating-fg)]",
  success: "bg-[var(--color-status-open-bg)] text-[var(--color-status-open-fg)]",
  warning: "bg-[var(--color-status-waiting-bg)] text-[var(--color-status-waiting-fg)]",
  danger: "bg-[var(--color-priority-high-bg)] text-[var(--color-priority-high-fg)]",
  info: "bg-[var(--color-status-investigating-bg)] text-[var(--color-status-investigating-fg)]",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  dot?: boolean;
  className?: string;
}

export function Badge({ children, variant = "default", dot = false, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full",
        "text-[11px] font-semibold uppercase tracking-wide",
        VARIANT_CLASSES[variant],
        className,
      )}
    >
      {dot && (
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{ backgroundColor: "currentColor" }}
        />
      )}
      {children}
    </span>
  );
}

type StatusKey = "OPEN" | "INVESTIGATING" | "WAITING" | "CLOSED";
type PriorityKey = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

const STATUS_STYLES: Record<StatusKey, string> = {
  OPEN: "bg-[var(--color-status-open-bg)] text-[var(--color-status-open-fg)]",
  INVESTIGATING:
    "bg-[var(--color-status-investigating-bg)] text-[var(--color-status-investigating-fg)]",
  WAITING: "bg-[var(--color-status-waiting-bg)] text-[var(--color-status-waiting-fg)]",
  CLOSED: "bg-[var(--color-status-closed-bg)] text-[var(--color-status-closed-fg)]",
};

const PRIORITY_STYLES: Record<PriorityKey, string> = {
  LOW: "bg-[var(--color-priority-low-bg)] text-[var(--color-priority-low-fg)]",
  MEDIUM: "bg-[var(--color-priority-medium-bg)] text-[var(--color-priority-medium-fg)]",
  HIGH: "bg-[var(--color-priority-high-bg)] text-[var(--color-priority-high-fg)]",
  CRITICAL: "bg-[var(--color-priority-critical-bg)] text-[var(--color-priority-critical-fg)]",
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = status.toUpperCase() as StatusKey;
  const styles = STATUS_STYLES[key] ?? STATUS_STYLES.CLOSED;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full",
        "text-[11px] font-semibold uppercase tracking-wide",
        styles,
        className,
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "currentColor" }} />
      {status}
    </span>
  );
}

interface PriorityBadgeProps {
  priority: string;
  className?: string;
}

export function PriorityBadge({ priority, className }: PriorityBadgeProps) {
  const key = priority.toUpperCase() as PriorityKey;
  const styles = PRIORITY_STYLES[key] ?? PRIORITY_STYLES.LOW;
  const dotColor =
    key === "CRITICAL" ? "var(--color-priority-critical-dot)" : "currentColor";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full",
        "text-[11px] font-semibold uppercase tracking-wide",
        styles,
        className,
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: dotColor }} />
      {priority}
    </span>
  );
}
