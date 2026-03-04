import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, Loader2 } from "lucide-react";
import type {
  PaginatedResponse,
  AutomationItem,
  ScheduledJobItem,
  ScheduleType,
  CalendarConfig,
} from "@/types/api";

const DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
];

interface JobFormModalProps {
  job?: ScheduledJobItem | null;
  onClose: () => void;
}

interface JobFormState {
  name: string;
  description: string;
  automation_id: string;
  schedule_type: ScheduleType;
  // Interval
  interval_value: number;
  interval_unit: "minutes" | "hours" | "days";
  // Cron
  cron_expression: string;
  // Calendar
  cal_days_of_week: number[];
  cal_days_of_month: number[];
  cal_months: number[];
  cal_time: string;
  // Common
  timezone: string;
  parameters: string;
  start_date: string;
  end_date: string;
}

function intervalToSeconds(value: number, unit: "minutes" | "hours" | "days"): number {
  if (unit === "minutes") return value * 60;
  if (unit === "hours") return value * 3600;
  return value * 86400;
}

function secondsToInterval(seconds: number): { value: number; unit: "minutes" | "hours" | "days" } {
  if (seconds % 86400 === 0) return { value: seconds / 86400, unit: "days" };
  if (seconds % 3600 === 0) return { value: seconds / 3600, unit: "hours" };
  return { value: seconds / 60, unit: "minutes" };
}

export function JobFormModal({ job, onClose }: JobFormModalProps) {
  const queryClient = useQueryClient();
  const isEdit = !!job;

  // Fetch active automations for the dropdown
  const { data: automationsData } = useQuery({
    queryKey: ["automations", { status: "active" }],
    queryFn: () => api.get<PaginatedResponse<AutomationItem>>("/automations?status=active&per_page=100"),
  });

  const initialInterval = job?.interval_seconds ? secondsToInterval(job.interval_seconds) : { value: 5, unit: "minutes" as const };

  const [form, setForm] = useState<JobFormState>({
    name: job?.name || "",
    description: job?.description || "",
    automation_id: job?.automation_id || "",
    schedule_type: job?.schedule_type || "interval",
    interval_value: initialInterval.value,
    interval_unit: initialInterval.unit,
    cron_expression: job?.cron_expression || "0 9 * * *",
    cal_days_of_week: job?.calendar_config?.days_of_week || [],
    cal_days_of_month: job?.calendar_config?.days_of_month || [],
    cal_months: job?.calendar_config?.months || [],
    cal_time: job?.calendar_config?.time || "09:00",
    timezone: job?.timezone || "UTC",
    parameters: job ? JSON.stringify(job, null, 2) : "{}",
    start_date: job?.start_date ? job.start_date.slice(0, 16) : "",
    end_date: job?.end_date ? job.end_date.slice(0, 16) : "",
  });

  // Fix: use actual parameters from job, not the full job object
  useEffect(() => {
    if (job) {
      setForm((prev) => ({
        ...prev,
        parameters: JSON.stringify(
          // The API returns the full job object, but we only want the parameters field
          (job as unknown as { parameters?: Record<string, unknown> }).parameters || {},
          null,
          2
        ),
      }));
    }
  }, [job]);

  const buildPayload = () => {
    let params: Record<string, unknown> = {};
    try {
      params = JSON.parse(form.parameters);
    } catch {
      // keep empty
    }

    const base: Record<string, unknown> = {
      name: form.name,
      description: form.description || null,
      automation_id: form.automation_id,
      schedule_type: form.schedule_type,
      timezone: form.timezone,
      parameters: params,
      start_date: form.start_date ? new Date(form.start_date).toISOString() : null,
      end_date: form.end_date ? new Date(form.end_date).toISOString() : null,
    };

    if (form.schedule_type === "interval") {
      base.interval_seconds = intervalToSeconds(form.interval_value, form.interval_unit);
      base.cron_expression = null;
      base.calendar_config = null;
    } else if (form.schedule_type === "cron") {
      base.cron_expression = form.cron_expression;
      base.interval_seconds = null;
      base.calendar_config = null;
    } else {
      const cal: CalendarConfig = {
        days_of_week: form.cal_days_of_week,
        days_of_month: form.cal_days_of_month,
        months: form.cal_months,
        time: form.cal_time,
      };
      base.calendar_config = cal;
      base.cron_expression = null;
      base.interval_seconds = null;
    }

    return base;
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = buildPayload();
      if (isEdit) {
        return api.patch(`/jobs/${job!.id}`, payload);
      }
      return api.post("/jobs", payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      onClose();
    },
  });

  const toggleDayOfWeek = (day: number) => {
    setForm((prev) => ({
      ...prev,
      cal_days_of_week: prev.cal_days_of_week.includes(day)
        ? prev.cal_days_of_week.filter((d) => d !== day)
        : [...prev.cal_days_of_week, day].sort(),
    }));
  };

  const toggleDayOfMonth = (day: number) => {
    setForm((prev) => ({
      ...prev,
      cal_days_of_month: prev.cal_days_of_month.includes(day)
        ? prev.cal_days_of_month.filter((d) => d !== day)
        : [...prev.cal_days_of_month, day].sort(),
    }));
  };

  const applyPreset = (preset: string) => {
    if (preset === "weekdays") {
      setForm((prev) => ({ ...prev, cal_days_of_week: [0, 1, 2, 3, 4], cal_days_of_month: [] }));
    } else if (preset === "monday") {
      setForm((prev) => ({ ...prev, cal_days_of_week: [0], cal_days_of_month: [] }));
    } else if (preset === "first_of_month") {
      setForm((prev) => ({ ...prev, cal_days_of_month: [1], cal_days_of_week: [] }));
    } else if (preset === "daily") {
      setForm((prev) => ({ ...prev, cal_days_of_week: [0, 1, 2, 3, 4, 5, 6], cal_days_of_month: [] }));
    }
  };

  const isValid =
    form.name.trim() &&
    form.automation_id &&
    (form.schedule_type !== "cron" || form.cron_expression.trim()) &&
    (form.schedule_type !== "interval" || form.interval_value > 0) &&
    (form.schedule_type !== "calendar" || form.cal_days_of_week.length > 0 || form.cal_days_of_month.length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--background))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[600px] max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-[hsl(var(--border))]">
          <h2 className="text-sm font-semibold">{isEdit ? "Edit Job" : "Create Scheduled Job"}</h2>
          <button onClick={onClose} className="p-1 hover:bg-[hsl(var(--accent))] rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-xs font-medium mb-1">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Daily threat report"
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-medium mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm"
              rows={2}
              placeholder="Optional description"
            />
          </div>

          {/* Automation selector */}
          <div>
            <label className="block text-xs font-medium mb-1">Automation</label>
            <select
              value={form.automation_id}
              onChange={(e) => setForm({ ...form, automation_id: e.target.value })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm"
            >
              <option value="">Select an automation...</option>
              {automationsData?.data.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>

          {/* Schedule type tabs */}
          <div>
            <label className="block text-xs font-medium mb-2">Schedule</label>
            <div className="flex border border-[hsl(var(--border))] rounded-md overflow-hidden mb-3">
              {(["interval", "calendar", "cron"] as ScheduleType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => setForm({ ...form, schedule_type: type })}
                  className={`flex-1 px-3 py-2 text-xs font-medium transition-colors ${
                    form.schedule_type === type
                      ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                      : "hover:bg-[hsl(var(--accent))]"
                  }`}
                >
                  {type === "interval" ? "Simple Interval" : type === "calendar" ? "Calendar" : "Cron Expression"}
                </button>
              ))}
            </div>

            {/* Interval config */}
            {form.schedule_type === "interval" && (
              <div className="flex items-center gap-2">
                <span className="text-sm">Every</span>
                <input
                  type="number"
                  min={1}
                  value={form.interval_value}
                  onChange={(e) => setForm({ ...form, interval_value: Math.max(1, Number(e.target.value)) })}
                  className="w-20 px-2 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
                />
                <select
                  value={form.interval_unit}
                  onChange={(e) => setForm({ ...form, interval_unit: e.target.value as "minutes" | "hours" | "days" })}
                  className="px-2 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
                >
                  <option value="minutes">minutes</option>
                  <option value="hours">hours</option>
                  <option value="days">days</option>
                </select>
              </div>
            )}

            {/* Calendar config */}
            {form.schedule_type === "calendar" && (
              <div className="space-y-3">
                {/* Presets */}
                <div>
                  <label className="block text-xs text-[hsl(var(--muted-foreground))] mb-1">Quick presets</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {[
                      { id: "weekdays", label: "Every Weekday" },
                      { id: "monday", label: "Every Monday" },
                      { id: "first_of_month", label: "1st of Month" },
                      { id: "daily", label: "Every Day" },
                    ].map((p) => (
                      <button
                        key={p.id}
                        onClick={() => applyPreset(p.id)}
                        className="px-2.5 py-1 text-xs border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))]"
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Day of week picker */}
                <div>
                  <label className="block text-xs text-[hsl(var(--muted-foreground))] mb-1">Days of week</label>
                  <div className="flex gap-1">
                    {DAYS_OF_WEEK.map((label, idx) => (
                      <button
                        key={idx}
                        onClick={() => toggleDayOfWeek(idx)}
                        className={`w-10 h-8 text-xs rounded-md border transition-colors ${
                          form.cal_days_of_week.includes(idx)
                            ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] border-[hsl(var(--primary))]"
                            : "border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Day of month picker */}
                <div>
                  <label className="block text-xs text-[hsl(var(--muted-foreground))] mb-1">Days of month</label>
                  <div className="grid grid-cols-7 gap-1">
                    {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => (
                      <button
                        key={day}
                        onClick={() => toggleDayOfMonth(day)}
                        className={`h-7 text-xs rounded transition-colors ${
                          form.cal_days_of_month.includes(day)
                            ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                            : "border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                        }`}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Time */}
                <div>
                  <label className="block text-xs text-[hsl(var(--muted-foreground))] mb-1">Time (24h)</label>
                  <input
                    type="time"
                    value={form.cal_time}
                    onChange={(e) => setForm({ ...form, cal_time: e.target.value })}
                    className="px-3 py-1.5 border border-[hsl(var(--input))] rounded-md text-sm"
                  />
                </div>
              </div>
            )}

            {/* Cron config */}
            {form.schedule_type === "cron" && (
              <div className="space-y-2">
                <input
                  value={form.cron_expression}
                  onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
                  placeholder="0 9 * * 1-5"
                  className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm font-mono"
                />
                <p className="text-xs text-[hsl(var(--muted-foreground))]">
                  Format: <code className="bg-[hsl(var(--muted))] px-1 rounded">minute hour day-of-month month day-of-week</code>
                </p>
                <div className="text-xs text-[hsl(var(--muted-foreground))] space-y-0.5">
                  <p>Examples:</p>
                  <p><code className="bg-[hsl(var(--muted))] px-1 rounded">0 9 * * *</code> — Every day at 9:00 AM</p>
                  <p><code className="bg-[hsl(var(--muted))] px-1 rounded">0 9 * * 1</code> — Every Monday at 9:00 AM</p>
                  <p><code className="bg-[hsl(var(--muted))] px-1 rounded">0 0 1 * *</code> — 1st of every month at midnight</p>
                  <p><code className="bg-[hsl(var(--muted))] px-1 rounded">*/15 * * * *</code> — Every 15 minutes</p>
                </div>
              </div>
            )}
          </div>

          {/* Timezone */}
          <div>
            <label className="block text-xs font-medium mb-1">Timezone</label>
            <select
              value={form.timezone}
              onChange={(e) => setForm({ ...form, timezone: e.target.value })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm"
            >
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>

          {/* Parameters */}
          <div>
            <label className="block text-xs font-medium mb-1">Parameters (JSON)</label>
            <textarea
              value={form.parameters}
              onChange={(e) => setForm({ ...form, parameters: e.target.value })}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm font-mono"
              rows={3}
              placeholder="{}"
            />
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium mb-1">Start Date (optional)</label>
              <input
                type="datetime-local"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">End Date (optional)</label>
              <input
                type="datetime-local"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm"
              />
            </div>
          </div>

          {saveMutation.isError && (
            <p className="text-xs text-red-500">Failed to save. Please check your schedule configuration.</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-[hsl(var(--border))]">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-xs rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!isValid || saveMutation.isPending}
            className="px-3 py-1.5 text-xs rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
          >
            {saveMutation.isPending && <Loader2 className="w-3 h-3 animate-spin inline mr-1" />}
            {isEdit ? "Save Changes" : "Create Job"}
          </button>
        </div>
      </div>
    </div>
  );
}
