import { cn } from "@/lib/utils";

interface Props {
  title: string;
  action?: React.ReactNode;
  className?: string;
}

export function SectionHeader({ title, action, className }: Props) {
  return (
    <div className={cn("flex items-center justify-between mb-3", className)}>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
        {title}
      </h3>
      {action}
    </div>
  );
}
