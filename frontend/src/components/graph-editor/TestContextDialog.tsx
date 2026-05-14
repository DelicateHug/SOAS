/**
 * Dialog for configuring test context before running a test.
 * Allows setting up mock incident data, parameters, and viewing SOAS variables.
 */

import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  X,
  Plus,
  Trash2,
  Play,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { TestContext } from "./hooks/useTestRun";

interface IncidentVariableDef {
  id: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number };
}

interface TestContextDialogProps {
  onRun: (context: TestContext) => void;
  onCancel: () => void;
  isRunning: boolean;
}

const SEVERITY_OPTIONS = ["low", "medium", "high", "critical"];
const STATUS_OPTIONS = [
  "detected",
  "triaging",
  "investigating",
  "containing",
  "remediating",
];

export default function TestContextDialog({
  onRun,
  onCancel,
  isRunning,
}: TestContextDialogProps) {
  // Mock incident state
  const [useMockIncident, setUseMockIncident] = useState(false);
  const [incidentTitle, setIncidentTitle] = useState("Test Incident");
  const [incidentSeverity, setIncidentSeverity] = useState("medium");
  const [incidentStatus, setIncidentStatus] = useState("investigating");
  const [incidentTags, setIncidentTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [customVars, setCustomVars] = useState<
    { key: string; value: string }[]
  >([]);

  // Fetch incident variable definitions to auto-populate custom vars
  const { data: incidentVarDefs } = useQuery({
    queryKey: ["incident-variables", "list"],
    queryFn: () =>
      api.get<PaginatedResponse<IncidentVariableDef>>(
        "/incident-variables?per_page=100"
      ),
    staleTime: 30_000,
  });

  // Auto-populate custom vars with default-enabled incident variables
  const [autoPopulated, setAutoPopulated] = useState(false);
  useEffect(() => {
    if (incidentVarDefs?.data && !autoPopulated) {
      const defaults = incidentVarDefs.data
        .filter((v) => v.default_enabled)
        .map((v) => ({ key: v.name, value: "" }));
      if (defaults.length > 0) {
        setCustomVars(defaults);
        setAutoPopulated(true);
      }
    }
  }, [incidentVarDefs, autoPopulated]);

  // Parameters state
  const [showParams, setShowParams] = useState(false);
  const [params, setParams] = useState<{ key: string; value: string }[]>([]);

  const handleAddTag = useCallback(() => {
    const tag = tagInput.trim();
    if (tag && !incidentTags.includes(tag)) {
      setIncidentTags((prev) => [...prev, tag]);
      setTagInput("");
    }
  }, [tagInput, incidentTags]);

  const handleRemoveTag = useCallback((tag: string) => {
    setIncidentTags((prev) => prev.filter((t) => t !== tag));
  }, []);

  const handleAddCustomVar = useCallback(() => {
    setCustomVars((prev) => [...prev, { key: "", value: "" }]);
  }, []);

  const handleRemoveCustomVar = useCallback((index: number) => {
    setCustomVars((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleAddParam = useCallback(() => {
    setParams((prev) => [...prev, { key: "", value: "" }]);
  }, []);

  const handleRemoveParam = useCallback((index: number) => {
    setParams((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleRun = useCallback(() => {
    const context: TestContext = {};

    if (useMockIncident) {
      const varsObj: Record<string, unknown> = {};
      for (const cv of customVars) {
        if (cv.key.trim()) {
          try {
            varsObj[cv.key.trim()] = JSON.parse(cv.value);
          } catch {
            varsObj[cv.key.trim()] = cv.value;
          }
        }
      }
      context.mockIncident = {
        title: incidentTitle,
        severity: incidentSeverity,
        status: incidentStatus,
        tags: incidentTags,
        custom_vars: varsObj,
      };
    }

    if (params.length > 0) {
      const paramsObj: Record<string, unknown> = {};
      for (const p of params) {
        if (p.key.trim()) {
          try {
            paramsObj[p.key.trim()] = JSON.parse(p.value);
          } catch {
            paramsObj[p.key.trim()] = p.value;
          }
        }
      }
      context.parameters = paramsObj;
    }

    onRun(context);
  }, [
    useMockIncident,
    incidentTitle,
    incidentSeverity,
    incidentStatus,
    incidentTags,
    customVars,
    params,
    onRun,
  ]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-xl w-[520px] max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-sm font-semibold">Test Context</h2>
          <button
            onClick={onCancel}
            className="p-1 rounded hover:bg-[var(--color-surface-2)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Quick Run Notice */}
          <div className="flex items-start gap-2 p-2 rounded bg-[var(--color-surface-2)]/50 text-xs text-[var(--color-text-muted)]">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>
              Configure test context for incident variables and parameters.
              Without a mock incident, incident variable nodes will return
              defaults.
            </span>
          </div>

          {/* Mock Incident Section */}
          <div className="space-y-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={useMockIncident}
                onChange={(e) => setUseMockIncident(e.target.checked)}
                className="rounded border-[var(--color-border)]"
              />
              <span className="text-sm font-medium">Use Mock Incident</span>
            </label>

            {useMockIncident && (
              <div className="space-y-3 pl-6 border-l-2 border-[var(--color-border)] ml-1">
                {/* Title */}
                <div>
                  <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                    Title
                  </label>
                  <input
                    type="text"
                    value={incidentTitle}
                    onChange={(e) => setIncidentTitle(e.target.value)}
                    className="w-full px-2 py-1.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                  />
                </div>

                {/* Severity + Status */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                      Severity
                    </label>
                    <select
                      value={incidentSeverity}
                      onChange={(e) => setIncidentSeverity(e.target.value)}
                      className="w-full px-2 py-1.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                    >
                      {SEVERITY_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                      Status
                    </label>
                    <select
                      value={incidentStatus}
                      onChange={(e) => setIncidentStatus(e.target.value)}
                      className="w-full px-2 py-1.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Tags */}
                <div>
                  <label className="text-xs text-[var(--color-text-muted)] mb-1 block">
                    Tags
                  </label>
                  <div className="flex flex-wrap gap-1 mb-1">
                    {incidentTags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-blue-500/20 text-blue-400"
                      >
                        {tag}
                        <button
                          onClick={() => handleRemoveTag(tag)}
                          className="hover:text-red-400"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-1">
                    <input
                      type="text"
                      value={tagInput}
                      onChange={(e) => setTagInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleAddTag()}
                      placeholder="Add tag..."
                      className="flex-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                    />
                    <button
                      onClick={handleAddTag}
                      className="px-2 py-1 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                    >
                      <Plus className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                {/* Incident Variables */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-[var(--color-text-muted)]">
                      Incident Variables
                    </label>
                    <button
                      onClick={handleAddCustomVar}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
                    >
                      <Plus className="w-3 h-3" /> Add
                    </button>
                  </div>
                  <div className="space-y-1">
                    {customVars.map((cv, i) => (
                      <div key={i} className="flex gap-1 items-center">
                        <input
                          type="text"
                          value={cv.key}
                          onChange={(e) =>
                            setCustomVars((prev) =>
                              prev.map((item, idx) =>
                                idx === i
                                  ? { ...item, key: e.target.value }
                                  : item
                              )
                            )
                          }
                          placeholder="Key"
                          className="flex-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                        />
                        <input
                          type="text"
                          value={cv.value}
                          onChange={(e) =>
                            setCustomVars((prev) =>
                              prev.map((item, idx) =>
                                idx === i
                                  ? { ...item, value: e.target.value }
                                  : item
                              )
                            )
                          }
                          placeholder="Value"
                          className="flex-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                        />
                        <button
                          onClick={() => handleRemoveCustomVar(i)}
                          className="p-1 text-red-400 hover:text-red-300"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Parameters Section (collapsible) */}
          <div>
            <button
              onClick={() => setShowParams(!showParams)}
              className="flex items-center gap-1 text-sm font-medium hover:text-[var(--color-text)] text-[var(--color-text-muted)]"
            >
              {showParams ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
              Parameters
            </button>
            {showParams && (
              <div className="mt-2 space-y-1 pl-5">
                {params.map((p, i) => (
                  <div key={i} className="flex gap-1 items-center">
                    <input
                      type="text"
                      value={p.key}
                      onChange={(e) =>
                        setParams((prev) =>
                          prev.map((item, idx) =>
                            idx === i
                              ? { ...item, key: e.target.value }
                              : item
                          )
                        )
                      }
                      placeholder="Key"
                      className="flex-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                    />
                    <input
                      type="text"
                      value={p.value}
                      onChange={(e) =>
                        setParams((prev) =>
                          prev.map((item, idx) =>
                            idx === i
                              ? { ...item, value: e.target.value }
                              : item
                          )
                        )
                      }
                      placeholder="Value (JSON or string)"
                      className="flex-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)]"
                    />
                    <button
                      onClick={() => handleRemoveParam(i)}
                      className="p-1 text-red-400 hover:text-red-300"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={handleAddParam}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
                >
                  <Plus className="w-3 h-3" /> Add Parameter
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[var(--color-border)]">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleRun}
            disabled={isRunning}
            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            Run Test
          </button>
        </div>
      </div>
    </div>
  );
}
