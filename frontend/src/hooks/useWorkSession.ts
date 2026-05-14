/**
 * Current work-session hook + mutations.
 *
 * Use:
 *   const { current, start, stop, pause, resume } = useWorkSession();
 *   start.mutate({ incident_id });           // or { case_id }
 *   if (current) { ... show timer ... }
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface WorkSessionData {
  id: string;
  user_id: string;
  incident_id: string | null;
  case_id: string | null;
  status: "active" | "paused" | "closed";
  started_at: string | null;
  active_since: string | null;
  paused_at: string | null;
  ended_at: string | null;
  accumulated_seconds: number;
  note: string | null;
  /** Total seconds including the currently-running segment. Updated server-side. */
  live_seconds: number;
}

export interface StartBody {
  incident_id?: string;
  case_id?: string;
  note?: string;
}

const CURRENT_KEY = ["work-session", "current"] as const;

export function useWorkSession() {
  const qc = useQueryClient();

  const current = useQuery({
    queryKey: CURRENT_KEY,
    queryFn: () => api.get<WorkSessionData | null>("/work-sessions/current"),
    refetchInterval: 30_000,
    // Re-fetch on tab focus so the sidebar timer doesn't drift if the
    // user was away.
    refetchOnWindowFocus: true,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["work-session"] });

  const start = useMutation({
    mutationFn: (body: StartBody) =>
      api.post<WorkSessionData>("/work-sessions/start", body),
    onSuccess: invalidate,
  });

  const pause = useMutation({
    mutationFn: (id: string) =>
      api.post<WorkSessionData>(`/work-sessions/${id}/pause`),
    onSuccess: invalidate,
  });

  const resume = useMutation({
    mutationFn: (id: string) =>
      api.post<WorkSessionData>(`/work-sessions/${id}/resume`),
    onSuccess: invalidate,
  });

  const stop = useMutation({
    mutationFn: (id: string) =>
      api.post<WorkSessionData>(`/work-sessions/${id}/stop`),
    onSuccess: invalidate,
  });

  return {
    current: current.data ?? null,
    isLoading: current.isLoading,
    start,
    pause,
    resume,
    stop,
  };
}
