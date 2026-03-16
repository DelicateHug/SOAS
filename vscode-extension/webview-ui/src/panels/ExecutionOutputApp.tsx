/**
 * Execution output webview panel app.
 * Shows live streaming output via WebSocket bridge.
 */

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface ExecutionDetail {
  id: string;
  automation_id: string;
  automation_name?: string;
  status: string;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  error_message: string | null;
  duration_ms: number | null;
  created_at: string;
}

interface Props {
  executionId: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--vscode-charts-yellow)",
  queued: "var(--vscode-charts-yellow)",
  running: "var(--vscode-charts-blue)",
  completed: "var(--vscode-charts-green)",
  failed: "var(--vscode-charts-red)",
  cancelled: "var(--vscode-charts-orange)",
  timed_out: "var(--vscode-charts-red)",
};

export function ExecutionOutputApp({ executionId }: Props) {
  const [liveOutput, setLiveOutput] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);

  const { data: execution, refetch } = useQuery({
    queryKey: ["execution", executionId],
    queryFn: () => api.get<ExecutionDetail>(`/executions/${executionId}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "running" || status === "pending" || status === "queued") return 2000;
      return false;
    },
  });

  // Connect WebSocket for live streaming
  useEffect(() => {
    if (!executionId) return;

    const ws = new WebSocket(`/api/v1/ws/executions/${executionId}`);
    setIsStreaming(true);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "output") {
          setLiveOutput((prev) => [...prev, msg.data]);
        } else if (msg.type === "complete" || msg.type === "status") {
          if (msg.status === "completed" || msg.status === "failed") {
            setIsStreaming(false);
            refetch();
          }
        }
      } catch {
        setLiveOutput((prev) => [...prev, event.data]);
      }
    };

    ws.onclose = () => {
      setIsStreaming(false);
    };

    ws.onerror = () => {
      setIsStreaming(false);
    };

    return () => ws.close();
  }, [executionId, refetch]);

  // Auto-scroll
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [liveOutput]);

  const status = execution?.status || "pending";
  const duration = execution?.duration_ms ? `${(execution.duration_ms / 1000).toFixed(1)}s` : "—";

  // Combine stored output with live output
  const displayOutput = execution?.stdout || liveOutput.join("\n") || "";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", color: "var(--vscode-foreground)", background: "var(--vscode-editor-background)" }}>
      {/* Header */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--vscode-panel-border)", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: STATUS_COLORS[status] || "gray",
          animation: isStreaming ? "pulse 1s infinite" : undefined,
        }} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>
          {execution?.automation_name || "Execution"}
        </span>
        <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)", textTransform: "capitalize" }}>
          {status}
        </span>
        <span style={{ fontSize: 12, color: "var(--vscode-descriptionForeground)", marginLeft: "auto" }}>
          Duration: {duration}
        </span>
        {execution?.exit_code !== null && execution?.exit_code !== undefined && (
          <span style={{
            fontSize: 12,
            color: execution.exit_code === 0 ? "var(--vscode-charts-green)" : "var(--vscode-charts-red)",
          }}>
            Exit: {execution.exit_code}
          </span>
        )}
      </div>

      {/* Output */}
      <div
        ref={outputRef}
        style={{
          flex: 1,
          padding: 16,
          fontFamily: "var(--vscode-editor-font-family)",
          fontSize: "var(--vscode-editor-font-size)",
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          overflow: "auto",
          background: "var(--vscode-terminal-background, var(--vscode-editor-background))",
          color: "var(--vscode-terminal-foreground, var(--vscode-editor-foreground))",
        }}
      >
        {displayOutput || (isStreaming ? "Waiting for output..." : "No output")}
      </div>

      {/* Error */}
      {execution?.stderr && (
        <div style={{
          padding: "8px 16px",
          background: "var(--vscode-inputValidation-errorBackground)",
          borderTop: "1px solid var(--vscode-inputValidation-errorBorder)",
          fontSize: 12,
          fontFamily: "var(--vscode-editor-font-family)",
          whiteSpace: "pre-wrap",
          maxHeight: 200,
          overflow: "auto",
        }}>
          <strong>stderr:</strong>{"\n"}{execution.stderr}
        </div>
      )}

      {execution?.error_message && (
        <div style={{
          padding: "8px 16px",
          background: "var(--vscode-inputValidation-errorBackground)",
          borderTop: "1px solid var(--vscode-inputValidation-errorBorder)",
          fontSize: 12,
          color: "var(--vscode-charts-red)",
        }}>
          {execution.error_message}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}
