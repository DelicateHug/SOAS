import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className }: CardProps) {
  return (
    <div
      className={cn(
        "bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function CardHeader({ children, action, className }: CardHeaderProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 px-4 py-3 border-b border-[var(--color-border)]",
        "bg-[var(--color-surface-2)] rounded-t-md",
        className,
      )}
    >
      <div className="text-sm font-semibold text-[var(--color-text)]">{children}</div>
      {action}
    </div>
  );
}

export function CardBody({ children, className }: CardProps) {
  return <div className={cn("p-4", className)}>{children}</div>;
}

export function CardFooter({ children, className }: CardProps) {
  return (
    <div
      className={cn(
        "px-4 py-2.5 border-t border-[var(--color-border)] bg-[var(--color-surface-2)] rounded-b-md",
        className,
      )}
    >
      {children}
    </div>
  );
}
