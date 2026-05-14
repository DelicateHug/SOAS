/**
 * Pill-group selector for switching between version tiers:
 * [Your Draft] [Dev] [Prod]
 *
 * Only visible in dev mode. Shows the current source tier and allows
 * switching to view different versions of an entity.
 */

import { cn } from "@/lib/utils";
import type { VersionTier } from "@/types/api";

interface TierSelectorProps {
  /** The currently active/displayed tier */
  currentTier: VersionTier;
  /** Which tier is manually selected (null = automatic/effective) */
  selectedTier: VersionTier | null;
  /** Callback to switch tiers */
  onSelect: (tier: VersionTier | null) => void;
  className?: string;
}

const TIERS: { value: VersionTier; label: string }[] = [
  { value: "user", label: "Your Draft" },
  { value: "dev", label: "Dev" },
  { value: "prod", label: "Prod" },
];

export function TierSelector({
  currentTier,
  selectedTier,
  onSelect,
  className,
}: TierSelectorProps) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      <span className="text-xs text-[var(--color-text-muted)] mr-1">
        Viewing:
      </span>
      {/* Auto (effective) button */}
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={cn(
          "px-2 py-0.5 rounded-full text-xs font-medium transition-colors",
          selectedTier === null
            ? "bg-[var(--color-primary)] text-[#ffffff]"
            : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)]",
        )}
      >
        Auto
      </button>
      {TIERS.map((t) => {
        const isActive = selectedTier === t.value;
        const isSource = selectedTier === null && currentTier === t.value;
        return (
          <button
            key={t.value}
            type="button"
            onClick={() => onSelect(t.value)}
            className={cn(
              "px-2 py-0.5 rounded-full text-xs font-medium transition-colors",
              isActive
                ? "bg-[var(--color-primary)] text-[#ffffff]"
                : isSource
                  ? "bg-[var(--color-surface-2)] text-[var(--color-text)] ring-1 ring-[var(--color-primary)]"
                  : "bg-[var(--color-surface-2)] text-[var(--color-text-muted)] hover:bg-[var(--color-surface-2)]",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
