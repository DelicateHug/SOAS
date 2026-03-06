import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/utils";
import { ArrowLeft, XCircle, Send, ChevronDown, ChevronRight } from "lucide-react";
import { DebugGraph } from "./DebugGraph";
import type { NodeTraceEntry } from "./DebugNodeComponent";

interface ExecutionDetail {
  id: string;
  automation_id: string;
  automation_name?: string;
  triggered_by: { id: string; username: string; display_name: string };
  incident_id?: string;
  case_id?: string;
  status: string;
  worker_id?: string;
  parameters: Record<string, unknown>;
  stdout?: string;
  stderr?: string;
  result_data?: Record<string, unknown>;
  exit_code?: number;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  error_message?: string;
  created_at: string;
}

interface PendingInput {
  requestId: string;
  nodeId: string;
  prompt: string;
  defaultValue: string;
}

const statusColors: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800",
  queued: "bg-blue-100 text-blue-800",
  running: "bg-yellow-100 text-yellow-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-500",
  timed_out: "bg-orange-100 text-orange-800",
};

export function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [liveOutput, setLiveOutput] = useState<string[]>([]);
  const [pendingInput, setPendingInput] = useState<PendingInput | null>(null);
  const [inputValue, setInputValue] = useState("");
  const outputRef = useRef<HTMLPreElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: execution, isLoading } = useQuery({
    queryKey: ["execution", id],
    queryFn: () => api.get<ExecutionDetail>(`/executions/${id}`),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "queued" || status === "pending" ? 3000 : false;
    },
  });

  const cancel = useToastMutation({
    mutationFn: () => api.post(`/executions/${id}/cancel`),
    loadingMessage: "Cancelling execution...",
    successMessage: "Execution cancelled.",
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["execution", id] }),
  });

  // WebSocket for live output and input handling
  useEffect(() => {
    if (!id || !execution) return;
    if (execution.status !== "running" && execution.status !== "queued") return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const token = api.getAccessToken();
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/executions/${id}${token ? `?token=${token}` : ""}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          type?: string;
          stream?: string;
          text?: string;
          line?: string;
          status?: string;
          request_id?: string;
          node_id?: string;
          prompt?: string;
          default?: string;
        };

        if (data.type === "output") {
          setLiveOutput((prev) => [...prev, data.text || data.line || ""]);
        } else if (data.type === "input_request" && data.request_id) {
          setLiveOutput((prev) => [
            ...prev,
            `[Input requested] ${data.prompt || "Enter value:"}`,
          ]);
          setPendingInput({
            requestId: data.request_id,
            nodeId: data.node_id || "",
            prompt: data.prompt || "Enter value:",
            defaultValue: data.default || "",
          });
        } else if (data.type === "complete") {
          setPendingInput(null);
          queryClient.invalidateQueries({ queryKey: ["execution", id] });
        }
      } catch {
        setLiveOutput((prev) => [...prev, event.data]);
      }
    };

    ws.onerror = () => ws.close();

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [id, execution?.status, queryClient]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [liveOutput, execution?.stdout, pendingInput]);

  // Focus and pre-fill input when a prompt appears
  useEffect(() => {
    if (pendingInput) {
      setInputValue(pendingInput.defaultValue);
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    }
  }, [pendingInput]);

  const handleSubmitInput = () => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && pendingInput) {
      ws.send(
        JSON.stringify({
          type: "input_response",
          request_id: pendingInput.requestId,
          value: inputValue,
          cancelled: false,
        })
      );
      setLiveOutput((prev) => [...prev, `[Input submitted] ${inputValue}`]);
      setPendingInput(null);
      setInputValue("");
    }
  };

  const handleCancelInput = () => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && pendingInput) {
      ws.send(
        JSON.stringify({
          type: "input_response",
          request_id: pendingInput.requestId,
          value: "",
          cancelled: true,
        })
      );
      setLiveOutput((prev) => [...prev, "[Input cancelled]"]);
      setPendingInput(null);
      setInputValue("");
    }
  };

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmitInput();
    } else if (e.key === "Escape") {
      e.preventDefault();
      handleCancelInput();
    }
  };

  if (isLoading) return <div className="text-center py-8">Loading...</div>;
  if (!execution) return <div className="text-center py-8">Execution not found</div>;

  const isActive = execution.status === "running" || execution.status === "queued" || execution.status === "pending";
  const outputText = execution.stdout || liveOutput.join("\n") || "";

  // Extract debug data from result_data if present
  const debugData = execution.result_data?.debug as
    | { graph_data: Record<string, unknown>; node_trace: Record<string, NodeTraceEntry> }
    | undefined;

  return (
    <div className="max-w-4xl">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] mb-4"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span className={`px-2 py-1 rounded text-xs ${statusColors[execution.status]}`}>
              {execution.status}
            </span>
            {execution.exit_code != null && (
              <span className="text-sm text-[hsl(var(--muted-foreground))]">
                Exit code: {execution.exit_code}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold">
            {execution.automation_name || "Execution"} #{execution.id.slice(0, 8)}
          </h1>
        </div>
        {isActive && (
          <button
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending}
            className="flex items-center gap-2 px-4 py-2 border border-red-300 text-red-600 rounded-md hover:bg-red-50"
          >
            <XCircle className="w-4 h-4" /> Cancel
          </button>
        )}
      </div>

      {/* Metadata grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="border border-[hsl(var(--border))] rounded-lg p-3">
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Triggered By</p>
          <p className="font-medium text-sm">{execution.triggered_by.display_name}</p>
        </div>
        <div className="border border-[hsl(var(--border))] rounded-lg p-3">
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Duration</p>
          <p className="font-medium text-sm">
            {execution.duration_ms != null ? formatDuration(execution.duration_ms) : isActive ? "Running..." : "-"}
          </p>
        </div>
        <div className="border border-[hsl(var(--border))] rounded-lg p-3">
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Started</p>
          <p className="font-medium text-sm">
            {execution.started_at ? formatDate(execution.started_at) : "-"}
          </p>
        </div>
        <div className="border border-[hsl(var(--border))] rounded-lg p-3">
          <p className="text-xs text-[hsl(var(--muted-foreground))]">Worker</p>
          <p className="font-medium text-sm">{execution.worker_id || "-"}</p>
        </div>
      </div>

      {/* Parameters */}
      {Object.keys(execution.parameters).length > 0 && (
        <div className="border border-[hsl(var(--border))] rounded-lg mb-6">
          <div className="px-4 py-3 border-b border-[hsl(var(--border))]">
            <h2 className="font-semibold text-sm">Parameters</h2>
          </div>
          <pre className="p-4 text-sm font-mono overflow-x-auto">
            {JSON.stringify(execution.parameters, null, 2)}
          </pre>
        </div>
      )}

      {/* Output */}
      <div className="border border-[hsl(var(--border))] rounded-lg mb-6">
        <div className="px-4 py-3 border-b border-[hsl(var(--border))] flex items-center justify-between">
          <h2 className="font-semibold text-sm">Output</h2>
          {isActive && (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Live
            </span>
          )}
        </div>
        <pre
          ref={outputRef}
          className="p-4 text-sm font-mono bg-[hsl(var(--card))] max-h-96 overflow-auto whitespace-pre-wrap"
        >
          {outputText || "No output yet"}
        </pre>

        {/* Inline input prompt */}
        {pendingInput && (
          <div className="flex items-center gap-2 px-4 py-3 border-t border-yellow-300 bg-yellow-50">
            <span className="text-sm text-yellow-800 shrink-0 font-medium">
              {pendingInput.prompt}
            </span>
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleInputKeyDown}
              className="flex-1 px-3 py-1.5 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] font-mono focus:outline-none focus:border-yellow-500"
              placeholder={pendingInput.defaultValue || "Type your response..."}
            />
            <button
              onClick={handleSubmitInput}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-green-600 text-white rounded hover:bg-green-700"
              title="Submit (Enter)"
            >
              <Send className="w-3.5 h-3.5" /> Submit
            </button>
            <button
              onClick={handleCancelInput}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-red-300 text-red-600 rounded hover:bg-red-50"
              title="Cancel (Esc)"
            >
              <XCircle className="w-3.5 h-3.5" /> Cancel
            </button>
          </div>
        )}
      </div>

      {/* Stderr */}
      {execution.stderr && (
        <div className="border border-red-200 rounded-lg mb-6">
          <div className="px-4 py-3 border-b border-red-200 bg-red-50">
            <h2 className="font-semibold text-sm text-red-800">Errors</h2>
          </div>
          <pre className="p-4 text-sm font-mono text-red-700 max-h-64 overflow-auto whitespace-pre-wrap">
            {execution.stderr}
          </pre>
        </div>
      )}

      {/* Error message */}
      {execution.error_message && (
        <div className="border border-red-200 rounded-lg p-4 mb-6 bg-red-50 text-red-800 text-sm">
          {execution.error_message}
        </div>
      )}

      {/* Debug Graph */}
      {debugData && (
        <DebugGraphSection
          graphData={debugData.graph_data}
          nodeTrace={debugData.node_trace}
        />
      )}

      {/* Result data (non-debug) */}
      {execution.result_data &&
        !execution.result_data.debug &&
        Object.keys(execution.result_data).length > 0 && (
          <div className="border border-[hsl(var(--border))] rounded-lg">
            <div className="px-4 py-3 border-b border-[hsl(var(--border))]">
              <h2 className="font-semibold text-sm">Result Data</h2>
            </div>
            <pre className="p-4 text-sm font-mono overflow-x-auto">
              {JSON.stringify(execution.result_data, null, 2)}
            </pre>
          </div>
        )}
    </div>
  );
}

/** Collapsible wrapper for the debug graph */
function DebugGraphSection({
  graphData,
  nodeTrace,
}: {
  graphData: Record<string, unknown>;
  nodeTrace: Record<string, NodeTraceEntry>;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-6">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1 text-sm font-semibold text-[hsl(var(--foreground))] mb-2 hover:text-[hsl(var(--foreground))/80]"
      >
        {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Debug Graph
      </button>
      {expanded && <DebugGraph graphData={graphData} nodeTrace={nodeTrace} />}
    </div>
  );
}
