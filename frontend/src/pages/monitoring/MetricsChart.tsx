import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { HealthMetricSnapshot } from "@/types/api";

interface MetricsChartProps {
  componentType: string;
  componentId?: string;
  metricKey: string;
  label: string;
  hours?: number;
  color?: string;
}

export function MetricsChart({
  componentType,
  componentId,
  metricKey,
  label,
  hours = 24,
  color = "var(--color-primary)",
}: MetricsChartProps) {
  const queryHours = Math.max(Math.ceil(hours), 1);
  const params = new URLSearchParams({ hours: String(queryHours) });
  if (componentId) params.set("component_id", componentId);

  // Refetch more frequently for short time windows
  const refetchInterval = hours <= 1 ? 30_000 : 300_000;

  const { data: snapshots } = useQuery({
    queryKey: ["monitoring-metrics", componentType, componentId, queryHours],
    queryFn: () =>
      api.get<HealthMetricSnapshot[]>(
        `/monitoring/metrics/${componentType}?${params}`
      ),
    refetchInterval,
  });

  const chartData =
    snapshots?.map((s) => ({
      time: new Date(s.recorded_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      value: Number(s.metrics[metricKey]) || 0,
    })) ?? [];

  return (
    <div className="border border-[var(--color-border)] rounded-lg p-4">
      <h3 className="font-semibold text-sm mb-3">{label}</h3>
      {chartData.length === 0 ? (
        <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
          No data available
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <XAxis dataKey="time" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
