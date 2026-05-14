export interface DashboardWidgetData {
  id: string;
  title: string;
  widget_type: string;
  config: Record<string, unknown>;
  position: number;
  width: number;
  height: number;
}

export interface Dashboard {
  id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  layout: Record<string, unknown>;
  owner_id: string;
  team_id: string | null;
  widgets: DashboardWidgetData[];
}

export interface DashboardCreate {
  name: string;
  description?: string | null;
  is_public?: boolean;
  team_id?: string | null;
  layout?: Record<string, unknown>;
}

export interface WidgetCreate {
  title: string;
  widget_type: string;
  config: Record<string, unknown>;
  position?: number;
  width?: number;
  height?: number;
}

export interface WidgetResult {
  data: unknown;
  meta: Record<string, unknown>;
}

export const WIDGET_TYPES = [
  { value: "counter", label: "Counter (single number)" },
  { value: "top_n", label: "Top N (bar list)" },
  { value: "timeseries", label: "Timeseries (line)" },
  { value: "pie", label: "Pie / donut" },
  { value: "stacked_bar", label: "Stacked bar (split timeseries)" },
  { value: "table", label: "Table" },
  { value: "duration_stat", label: "Duration stat (MTTI / MTTR)" },
  { value: "ratio", label: "Ratio" },
  { value: "tokens_counter", label: "Token usage — counter" },
  { value: "tokens_top_n", label: "Token usage — top N" },
  { value: "tokens_timeseries", label: "Token usage — timeseries" },
  { value: "changes_counter", label: "Changes — counter" },
  { value: "changes_top_n", label: "Changes — top N" },
  { value: "changes_timeseries", label: "Changes — timeseries" },
] as const;

export const SOURCES = [
  { value: "incidents", label: "Incidents" },
  { value: "cases", label: "Incident groups" },
  { value: "token_usage", label: "Token usage" },
  { value: "artifact_changes", label: "Artifact changes" },
  { value: "executions", label: "Executions" },
] as const;

export const TIME_RANGES = [
  { value: "last_24h", label: "Last 24 hours" },
  { value: "last_7d", label: "Last 7 days" },
  { value: "last_30d", label: "Last 30 days (default)" },
  { value: "last_90d", label: "Last 90 days" },
] as const;
