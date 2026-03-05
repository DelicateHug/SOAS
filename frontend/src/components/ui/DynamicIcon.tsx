import {
  AlertTriangle,
  Book,
  Box,
  Bug,
  Calculator,
  Code,
  Database,
  File,
  Folder,
  GitBranch,
  Globe,
  Key,
  Layers,
  List,
  Rocket,
  Settings,
  Shield,
  Terminal,
  Type,
  Variable,
  Zap,
  HelpCircle,
} from "lucide-react";
import type { LucideProps } from "lucide-react";

const iconMap: Record<string, React.ComponentType<LucideProps>> = {
  "alert-triangle": AlertTriangle,
  book: Book,
  box: Box,
  bug: Bug,
  calculator: Calculator,
  code: Code,
  database: Database,
  file: File,
  folder: Folder,
  "git-branch": GitBranch,
  globe: Globe,
  key: Key,
  layers: Layers,
  list: List,
  rocket: Rocket,
  settings: Settings,
  shield: Shield,
  terminal: Terminal,
  type: Type,
  variable: Variable,
  zap: Zap,
};

export function DynamicIcon({
  name,
  className = "w-4 h-4",
}: {
  name: string | null | undefined;
  className?: string;
}) {
  if (!name) return null;
  const Icon = iconMap[name] || HelpCircle;
  return <Icon className={className} />;
}
