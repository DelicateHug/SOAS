/**
 * Hook for triggering a test run and streaming live output via WebSocket,
 * with HTTP polling fallback to detect completion.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useGraphEditorStore } from "../stores/graphEditorStore";
import { toBackendFormat } from "../utils/graphConversion";

export interface OutputLine {
  stream: "stdout" | "stderr" | "system";
  text: string;
  timestamp: string;
}

export type TestRunStatus = "idle" | "running" | "completed" | "failed";

interface ExecutionRecord {
  status: string;
  stdout?: string | null;
  stderr?: string | null;
  exit_code?: number | null;
  error_message?: string | null;
  duration_ms?: number | null;
}

export interface TestContext {
  mockIncident?: {
    title: string;
    severity: string;
    status: string;
    tags: string[];
    custom_vars: Record<string, unknown>;
  } | null;
  parameters?: Record<string, unknown>;
}

export interface InputRequest {
  requestId: string;
  nodeId: string;
  prompt: string;
  defaultValue: string;
}

export function useTestRun(automationId: string | undefined) {
  const {
    setIsTestRunning,
    setTestRunExecutionId,
    toVP2GraphData,
  } = useGraphEditorStore();

  const [outputLines, setOutputLines] = useState<OutputLine[]>([]);
  const [status, setStatus] = useState<TestRunStatus>("idle");
  const [pendingInput, setPendingInput] = useState<InputRequest | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const executionIdRef = useRef<string | null>(null);
  const statusRef = useRef<TestRunStatus>("idle");
  const completedRef = useRef(false);

  // Keep statusRef in sync
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const addSystemLine = useCallback((text: string) => {
    setOutputLines((prev) => [
      ...prev,
      { stream: "system" as const, text, timestamp: new Date().toISOString() },
    ]);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Fetch execution record and display stdout/stderr, then mark as complete
  const fetchOutputAndComplete = useCallback(
    async (executionId: string, hint?: { status?: string; exit_code?: number }) => {
      // Prevent double-completion
      if (completedRef.current) return;
      completedRef.current = true;
      stopPolling();

      try {
        const data = await api.get<ExecutionRecord>(`/executions/${executionId}`);

        // Only add stdout/stderr from HTTP if WebSocket didn't already stream them.
        // Check if we already have output lines (from WebSocket streaming).
        setOutputLines((prev) => {
          const hasStreamedOutput = prev.some((l) => l.stream === "stdout" || l.stream === "stderr");
          if (hasStreamedOutput) return prev; // WebSocket already streamed output

          const newLines: OutputLine[] = [];
          if (data.stdout) {
            for (const line of data.stdout.split("\n")) {
              if (line) {
                newLines.push({ stream: "stdout", text: line, timestamp: new Date().toISOString() });
              }
            }
          }
          if (data.stderr) {
            for (const line of data.stderr.split("\n")) {
              if (line) {
                newLines.push({ stream: "stderr", text: line, timestamp: new Date().toISOString() });
              }
            }
          }
          return [...prev, ...newLines];
        });

        const finalStatus = data.status || hint?.status || "completed";
        const exitCode = data.exit_code ?? hint?.exit_code ?? 0;
        const isSuccess = finalStatus === "completed" || (exitCode === 0 && finalStatus !== "timed_out");

        const msg =
          finalStatus === "timed_out"
            ? "Execution timed out"
            : isSuccess
              ? `Execution completed (exit code: ${exitCode}, ${data.duration_ms ?? 0}ms)`
              : `Execution failed: ${data.error_message || `exit code ${exitCode}`}`;

        setStatus(isSuccess ? "completed" : "failed");
        setIsTestRunning(false);
        addSystemLine(msg);
      } catch {
        // If fetch fails, use the hint info
        const isSuccess = hint?.status === "completed";
        setStatus(isSuccess ? "completed" : "failed");
        setIsTestRunning(false);
        addSystemLine(
          isSuccess
            ? `Execution completed (exit code: ${hint?.exit_code ?? 0})`
            : `Execution ${hint?.status || "failed"}`
        );
      }
    },
    [addSystemLine, setIsTestRunning, stopPolling]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      stopPolling();
    };
  }, [stopPolling]);

  // Poll execution status as fallback
  const startPolling = useCallback(
    (executionId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);

      pollRef.current = setInterval(async () => {
        if (statusRef.current !== "running" || completedRef.current) {
          stopPolling();
          return;
        }

        try {
          const data = await api.get<ExecutionRecord>(`/executions/${executionId}`);

          if (data.status === "completed" || data.status === "failed" || data.status === "timed_out") {
            fetchOutputAndComplete(executionId, { status: data.status, exit_code: data.exit_code ?? undefined });
          }
        } catch {
          // Polling error - keep trying
        }
      }, 2000);
    },
    [fetchOutputAndComplete, stopPolling]
  );

  const connectWebSocket = useCallback(
    (executionId: string) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/executions/${executionId}`;
      const token = api.getAccessToken();

      const ws = new WebSocket(`${wsUrl}?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        addSystemLine("Connected to execution stream...");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as {
            type?: string;
            stream?: "stdout" | "stderr";
            text?: string;
            status?: string;
            exit_code?: number;
            errors?: string[];
            request_id?: string;
            node_id?: string;
            prompt?: string;
            default?: string;
          };

          // Live output lines from streaming
          if (data.type === "output" && data.stream && data.text) {
            setOutputLines((prev) => [
              ...prev,
              {
                stream: data.stream!,
                text: data.text!,
                timestamp: new Date().toISOString(),
              },
            ]);
          }
          // Input request from subprocess — show prompt in UI
          else if (data.type === "input_request" && data.request_id) {
            addSystemLine(`Input requested: ${data.prompt || "Enter value:"}`);
            setPendingInput({
              requestId: data.request_id,
              nodeId: data.node_id || "",
              prompt: data.prompt || "Enter value:",
              defaultValue: data.default || "",
            });
          }
          // Completion: handle both "status" and "complete" type from worker
          else if (data.type === "status" || data.type === "complete") {
            setPendingInput(null);
            fetchOutputAndComplete(executionId, {
              status: data.status,
              exit_code: data.exit_code,
            });
          }
          // Compile errors from worker
          else if (data.type === "compile_error") {
            if (!completedRef.current) {
              completedRef.current = true;
              stopPolling();
              setPendingInput(null);
              const errMsg = data.errors?.join("; ") || "Compilation failed";
              setStatus("failed");
              setIsTestRunning(false);
              addSystemLine(`Compile error: ${errMsg}`);
            }
          }
        } catch {
          setOutputLines((prev) => [
            ...prev,
            {
              stream: "stdout",
              text: event.data as string,
              timestamp: new Date().toISOString(),
            },
          ]);
        }
      };

      ws.onerror = () => {
        addSystemLine("WebSocket error - falling back to polling...");
        if (executionIdRef.current) startPolling(executionIdRef.current);
      };

      ws.onclose = () => {
        // If execution is still running when WS closes, fall back to polling
        if (statusRef.current === "running" && !completedRef.current && executionIdRef.current) {
          startPolling(executionIdRef.current);
        }
      };
    },
    [addSystemLine, fetchOutputAndComplete, setIsTestRunning, startPolling, stopPolling]
  );

  const mutation = useMutation({
    mutationFn: async (testContext?: TestContext) => {
      if (!automationId) throw new Error("No automation ID");

      const graphData = toVP2GraphData();
      const backendData = toBackendFormat(graphData);

      const body: Record<string, unknown> = { graph_data: backendData };
      if (testContext?.mockIncident) {
        body.mock_incident = testContext.mockIncident;
      }
      if (testContext?.parameters && Object.keys(testContext.parameters).length > 0) {
        body.parameters = testContext.parameters;
      }

      return api.post<{ execution_id: string; status: string; compile_errors: string[] }>(
        `/automations/${automationId}/test-run`,
        body
      );
    },
    onMutate: () => {
      setOutputLines([]);
      setStatus("running");
      setIsTestRunning(true);
      completedRef.current = false;
    },
    onSuccess: (data) => {
      // Check for compile errors returned synchronously
      if (data.status === "compile_error" || (data.compile_errors && data.compile_errors.length > 0)) {
        completedRef.current = true;
        const errMsg = data.compile_errors?.join("; ") || "Compilation failed";
        setStatus("failed");
        setIsTestRunning(false);
        addSystemLine(`Compile error: ${errMsg}`);
        return;
      }

      if (!data.execution_id) {
        completedRef.current = true;
        setStatus("failed");
        setIsTestRunning(false);
        addSystemLine("No execution ID returned");
        return;
      }

      executionIdRef.current = data.execution_id;
      setTestRunExecutionId(data.execution_id);
      addSystemLine(`Execution queued (${data.execution_id})`);

      // Connect WebSocket for live streaming (polling starts only on WS failure)
      connectWebSocket(data.execution_id);
    },
    onError: (error: Error & { detail?: string }) => {
      completedRef.current = true;
      setStatus("failed");
      setIsTestRunning(false);
      addSystemLine(`Failed to start test run: ${error.detail || error.message}`);
    },
  });

  const respondToInput = useCallback(
    (requestId: string, value: string, cancelled: boolean) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            type: "input_response",
            request_id: requestId,
            value,
            cancelled,
          })
        );
      }
      setPendingInput(null);
    },
    []
  );

  const clearOutput = useCallback(() => {
    setOutputLines([]);
    setStatus("idle");
    setPendingInput(null);
    completedRef.current = false;
  }, []);

  return {
    startTestRun: mutation.mutate,
    isStarting: mutation.isPending,
    outputLines,
    status,
    pendingInput,
    respondToInput,
    clearOutput,
  };
}
