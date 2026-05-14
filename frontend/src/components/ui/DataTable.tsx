import { cn } from "@/lib/utils";

interface DataTableProps {
  children: React.ReactNode;
  className?: string;
}

export function DataTable({ children, className }: DataTableProps) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-[13px] border-separate border-spacing-0">
        {children}
      </table>
    </div>
  );
}

interface ThProps {
  children: React.ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}

export function Th({ children, className, align = "left" }: ThProps) {
  return (
    <th
      className={cn(
        "px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider",
        "text-[var(--color-text-muted)] bg-[var(--color-surface-2)]",
        "border-b border-[var(--color-border)]",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

interface TdProps {
  children: React.ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
}

export function Td({ children, className, align = "left" }: TdProps) {
  return (
    <td
      className={cn(
        "px-3 py-2.5 border-b border-[var(--color-border)] text-[var(--color-text)]",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
        className,
      )}
    >
      {children}
    </td>
  );
}

interface TrProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}

export function Tr({ children, className, onClick }: TrProps) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "transition-colors duration-100",
        "hover:bg-[var(--color-surface-subtle)]",
        onClick && "cursor-pointer",
        className,
      )}
    >
      {children}
    </tr>
  );
}
