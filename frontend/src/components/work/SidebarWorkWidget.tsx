/**
 * Sidebar work-session widget — pulsing green dot, live timer, link to the
 * target, continue/stop. Only renders when the user has an active or
 * paused session.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Play, Pause, Square } from "lucide-react";
import { useWorkSession } from "@/hooks/useWorkSession";

export function SidebarWorkWidget({ collapsed }: { collapsed: boolean }) {
  const { current, pause, resume, stop } = useWorkSession();
  if (!current) return null;
  if (collapsed) {
    return (
      <div className="xs-work-widget">
        <div className="xs-work-widget-row" style={{ justifyContent: "center" }}>
          <span className="xs-work-widget-dot" />
        </div>
      </div>
    );
  }

  const targetUrl = current.incident_id
    ? `/incidents/${current.incident_id}`
    : current.case_id
      ? `/cases/${current.case_id}`
      : "#";
  const targetLabel = current.incident_id ? "Incident" : "Case";

  return (
    <div className="xs-work-widget">
      <div className="xs-work-widget-row">
        <span className="xs-work-widget-dot" />
        <span className="xs-work-widget-label">
          {current.status === "active" ? "Working" : "Paused"}
        </span>
        {current.status === "active" ? (
          <LiveTimer baseSeconds={current.live_seconds} />
        ) : (
          <span className="xs-work-widget-timer">
            {formatDuration(current.accumulated_seconds)}
          </span>
        )}
      </div>
      <div className="xs-work-widget-row">
        <Link to={targetUrl} className="xs-work-widget-title" title={`Open ${targetLabel.toLowerCase()}`}>
          {targetLabel}
        </Link>
      </div>
      <div className="xs-work-widget-row">
        <Link
          to={targetUrl}
          className="xs-work-widget-case"
          title={current.incident_id ?? current.case_id ?? ""}
        >
          {(current.incident_id ?? current.case_id ?? "").slice(0, 8)}…
        </Link>
      </div>
      <div className="xs-work-widget-row xs-work-widget-actions">
        {current.status === "active" ? (
          <button
            className="xs-ws-btn"
            onClick={() => pause.mutate(current.id)}
            disabled={pause.isPending}
            title="Pause"
            aria-label="Pause"
          >
            <Pause size={11} />
          </button>
        ) : (
          <button
            className="xs-ws-btn xs-ws-continue"
            onClick={() => resume.mutate(current.id)}
            disabled={resume.isPending}
            title="Resume"
            aria-label="Resume"
          >
            <Play size={11} />
          </button>
        )}
        <button
          className="xs-ws-btn xs-ws-stop"
          onClick={() => stop.mutate(current.id)}
          disabled={stop.isPending}
          title="Stop"
          aria-label="Stop"
        >
          <Square size={11} />
        </button>
      </div>
    </div>
  );
}

function LiveTimer({ baseSeconds }: { baseSeconds: number }) {
  const [snapshot] = useState({ base: baseSeconds, at: Date.now() });
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const h = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(h);
  }, []);
  const elapsed = snapshot.base + Math.floor((now - snapshot.at) / 1000);
  return <span className="xs-work-widget-timer">{formatDuration(elapsed)}</span>;
}

function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  return `${m}:${String(ss).padStart(2, "0")}`;
}
