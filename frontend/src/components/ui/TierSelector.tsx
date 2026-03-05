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
      <span className="text-xs text-[hsl(var(--muted-foreground))] mr-1">
        Viewing:
      </span>
      {/* Auto (effective) button */}
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={cn(
          "px-2 py-0.5 rounded-full text-xs font-medium transition-colors",
          selectedTier === null
            ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
            : "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]",
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
                ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                : isSource
                  ? "bg-[hsl(var(--accent))] text-[hsl(var(--accent-foreground))] ring-1 ring-[hsl(var(--primary))]"
                  : "bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--accent))]",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
