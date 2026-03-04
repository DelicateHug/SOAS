import { cn } from "@/lib/utils";

interface Props {
  displayName: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizes = {
  sm: "h-6 w-6 text-[10px]",
  md: "h-8 w-8 text-xs",
  lg: "h-10 w-10 text-sm",
};

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function hashColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = [
    "bg-blue-600",
    "bg-purple-600",
    "bg-emerald-600",
    "bg-amber-600",
    "bg-rose-600",
    "bg-cyan-600",
    "bg-indigo-600",
    "bg-teal-600",
  ];
  return colors[Math.abs(hash) % colors.length]!;
}

export function UserAvatar({ displayName, size = "md", className }: Props) {
  return (
    <div
      className={cn(
        "inline-flex items-center justify-center rounded-full text-white font-medium shrink-0",
        sizes[size],
        hashColor(displayName),
        className,
      )}
      title={displayName}
    >
      {getInitials(displayName)}
    </div>
  );
}
