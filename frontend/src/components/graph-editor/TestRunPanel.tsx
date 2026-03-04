/**
 * Bottom panel showing test run output in a terminal-like display.
 * Connects via WebSocket for live streaming output.
 * Supports inline input prompts when the automation requests user input.
 */

import { useState, useRef, useEffect } from "react";
import { Terminal, Trash2, CircleDot, Send, XCircle } from "lucide-react";
import type { OutputLine, TestRunStatus, InputRequest } from "./hooks/useTestRun";

interface TestRunPanelProps {
  outputLines: OutputLine[];
  status: TestRunStatus;
  onClear: () => void;
  pendingInput: InputRequest | null;
  onSubmitInput: (value: string) => void;
  onCancelInput: () => void;
}

const statusConfig: Record<
  TestRunStatus,
  { label: string; className: string }
> = {
  idle: { label: "Idle", className: "text-[hsl(var(--muted-foreground))]" },
  running: { label: "Running", className: "text-yellow-500" },
  completed: { label: "Completed", className: "text-green-500" },
  failed: { label: "Failed", className: "text-red-500" },
};

export function TestRunPanel({
  outputLines,
  status,
  onClear,
  pendingInput,
  onSubmitInput,
  onCancelInput,
}: TestRunPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [inputValue, setInputValue] = useState("");

  // Auto-scroll to bottom on new output or when input prompt appears
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [outputLines, pendingInput]);

  // Focus and pre-fill input when a prompt appears
  useEffect(() => {
    if (pendingInput) {
      setInputValue(pendingInput.defaultValue);
      // Small delay to ensure the DOM has rendered the input
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    }
  }, [pendingInput]);

  const handleSubmit = () => {
    onSubmitInput(inputValue);
    setInputValue("");
  };

  const handleCancel = () => {
    onCancelInput();
    setInputValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      handleCancel();
    }
  };

  const statusInfo = statusConfig[status];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[hsl(var(--border))] bg-[hsl(var(--background))]">
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5" />
          <span className="text-xs font-semibold">Test Run Output</span>
          <div className="flex items-center gap-1">
            <CircleDot
              className={`w-3 h-3 ${statusInfo.className} ${
                status === "running" ? "animate-pulse" : ""
              }`}
            />
            <span className={`text-[10px] ${statusInfo.className}`}>
              {statusInfo.label}
            </span>
          </div>
        </div>
        <button
          onClick={onClear}
          className="p-1 hover:bg-[hsl(var(--accent))] rounded"
          title="Clear output"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>

      {/* Output area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-gray-950 font-mono text-xs p-2"
      >
        {outputLines.length === 0 ? (
          <div className="text-gray-500 text-center py-4">
            No output yet. Click &quot;Test Run&quot; to execute the graph.
          </div>
        ) : (
          outputLines.map((line, idx) => (
            <div key={idx} className="leading-5 whitespace-pre-wrap break-all">
              {line.stream === "stderr" ? (
                <span className="text-red-400">{line.text}</span>
              ) : line.stream === "system" ? (
                <span className="text-blue-400 italic">{line.text}</span>
              ) : (
                <span className="text-gray-200">{line.text}</span>
              )}
            </div>
          ))
        )}
      </div>

      {/* Inline input prompt */}
      {pendingInput && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-yellow-500/30 bg-yellow-500/10">
          <span className="text-xs text-yellow-400 shrink-0 font-medium">
            {pendingInput.prompt}
          </span>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 px-2 py-1 text-xs rounded border border-[hsl(var(--border))] bg-gray-900 text-gray-100 font-mono focus:outline-none focus:border-yellow-500"
            placeholder={pendingInput.defaultValue || "Type your response..."}
          />
          <button
            onClick={handleSubmit}
            className="p-1 text-green-400 hover:text-green-300"
            title="Submit (Enter)"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleCancel}
            className="p-1 text-red-400 hover:text-red-300"
            title="Cancel (Esc)"
          >
            <XCircle className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
