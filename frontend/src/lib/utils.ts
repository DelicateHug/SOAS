import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateUTC(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) + " UTC";
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

export const severityColors: Record<string, string> = {
  critical: "bg-red-500 text-white",
  high: "bg-orange-500 text-white",
  medium: "bg-yellow-500 text-black",
  low: "bg-blue-500 text-white",
  informational: "bg-gray-500 text-white",
};

export const statusColors: Record<string, string> = {
  detected: "bg-red-500/15 text-red-400",
  triaging: "bg-yellow-500/15 text-yellow-400",
  investigating: "bg-blue-500/15 text-blue-400",
  containing: "bg-purple-500/15 text-purple-400",
  remediating: "bg-indigo-500/15 text-indigo-400",
  resolved: "bg-green-500/15 text-green-400",
  closed: "bg-gray-500/15 text-gray-400",
  false_positive: "bg-gray-500/15 text-gray-500",
};

export const issueStatusColors: Record<string, string> = {
  open: "bg-blue-500/15 text-blue-400",
  in_progress: "bg-amber-500/15 text-amber-400",
  resolved: "bg-green-500/15 text-green-400",
  closed: "bg-gray-500/15 text-gray-400",
  wont_fix: "bg-red-500/15 text-red-400",
};

export const issueStatusLabels: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
  closed: "Closed",
  wont_fix: "Won't Fix",
};

export const statusDotColors: Record<string, string> = {
  detected: "bg-red-500",
  triaging: "bg-yellow-500",
  investigating: "bg-blue-500",
  containing: "bg-purple-500",
  remediating: "bg-indigo-500",
  resolved: "bg-green-500",
  closed: "bg-gray-500",
  false_positive: "bg-gray-400",
};

export const caseStatusColors: Record<string, string> = {
  open: "bg-green-500/15 text-green-400",
  investigating: "bg-blue-500/15 text-blue-400",
  pending: "bg-yellow-500/15 text-yellow-400",
  closed: "bg-gray-500/15 text-gray-400",
  archived: "bg-gray-500/15 text-gray-500",
};

export const priorityColors: Record<number, string> = {
  1: "bg-red-500 text-white",
  2: "bg-orange-500 text-white",
  3: "bg-yellow-500 text-black",
  4: "bg-blue-500 text-white",
  5: "bg-gray-500 text-white",
};

export const priorityLabels: Record<number, string> = {
  1: "P1 - Critical",
  2: "P2 - High",
  3: "P3 - Medium",
  4: "P4 - Low",
  5: "P5 - Minimal",
};
