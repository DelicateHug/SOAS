/**
 * Modal dialog for defining automation input parameters.
 * Allows users to specify typed inputs that other automations can provide
 * when using the Run Automation node.
 */

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  ListPlus,
  Loader2,
  X,
  Plus,
  Trash2,
  GripVertical,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type { AutomationInputDef } from "./AutomationSelectField";

const INPUT_TYPES = [
  "STRING",
  "INTEGER",
  "FLOAT",
  "BOOLEAN",
  "LIST",
  "DICT",
  "ANY",
] as const;

interface AutomationInputsDialogProps {
  automationId: string;
  onClose: () => void;
  onSave?: (inputs: AutomationInputDef[]) => void;
}

export function AutomationInputsDialog({
  automationId,
  onClose,
  onSave,
}: AutomationInputsDialogProps) {
  const queryClient = useQueryClient();

  const { data: automation, isLoading } = useQuery({
    queryKey: ["automation", automationId],
    queryFn: () =>
      api.get<{ parameters: AutomationInputDef[] }>(
        `/automations/${automationId}`
      ),
    enabled: !!automationId,
  });

  const [inputs, setInputs] = useState<AutomationInputDef[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  useEffect(() => {
    if (automation?.parameters) {
      setInputs(
        automation.parameters.map((p) => ({
          name: p.name || "",
          type: p.type || "STRING",
          required: p.required ?? true,
          default_value: p.default_value ?? null,
          description: p.description || "",
        }))
      );
      setIsDirty(false);
    }
  }, [automation]);

  const addInput = () => {
    setInputs((prev) => [
      ...prev,
      {
        name: "",
        type: "STRING",
        required: true,
        default_value: null,
        description: "",
      },
    ]);
    setIsDirty(true);
    setExpandedIndex(inputs.length);
  };

  const removeInput = (index: number) => {
    setInputs((prev) => prev.filter((_, i) => i !== index));
    setIsDirty(true);
    if (expandedIndex === index) setExpandedIndex(null);
    else if (expandedIndex !== null && expandedIndex > index)
      setExpandedIndex(expandedIndex - 1);
  };

  const updateInput = (
    index: number,
    field: keyof AutomationInputDef,
    value: unknown
  ) => {
    setInputs((prev) =>
      prev.map((input, i) =>
        i === index ? { ...input, [field]: value } : input
      )
    );
    setIsDirty(true);
  };

  const moveInput = (index: number, direction: -1 | 1) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= inputs.length) return;
    setInputs((prev) => {
      const next = [...prev];
      [next[index], next[newIndex]] = [next[newIndex]!, next[index]!];
      return next;
    });
    if (expandedIndex === index) setExpandedIndex(newIndex);
    else if (expandedIndex === newIndex) setExpandedIndex(index);
    setIsDirty(true);
  };

  // Validate inputs
  const validationErrors: string[] = [];
  const seenNames = new Set<string>();
  for (let i = 0; i < inputs.length; i++) {
    const input = inputs[i]!;
    if (!input.name) {
      validationErrors.push(`Input ${i + 1}: name is required`);
    } else if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(input.name)) {
      validationErrors.push(
        `Input ${i + 1}: name must be a valid identifier (letters, numbers, underscores)`
      );
    } else if (seenNames.has(input.name)) {
      validationErrors.push(`Input ${i + 1}: duplicate name "${input.name}"`);
    }
    if (input.name) seenNames.add(input.name);
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      return api.request(`/automations/${automationId}`, {
        method: "PATCH",
        body: JSON.stringify({ parameters: inputs }),
      });
    },
    onSuccess: () => {
      setIsDirty(false);
      onSave?.(inputs);
      queryClient.invalidateQueries({
        queryKey: ["automation", automationId],
      });
      queryClient.invalidateQueries({
        queryKey: ["automations", "addable"],
      });
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl w-[560px] max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-2.5">
            <ListPlus className="w-5 h-5 text-[var(--color-text-muted)]" />
            <h2 className="text-base font-semibold">Automation Inputs</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-[var(--color-surface-2)] rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--color-text-muted)]" />
            </div>
          ) : (
            <div className="space-y-2">
              {inputs.length === 0 && (
                <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                  No inputs defined yet.
                </p>
              )}

              {/* Column headers */}
              {inputs.length > 0 && (
                <div className="flex items-center gap-3 px-1 pb-1">
                  <div className="w-6" />
                  <span className="flex-1 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                    Name
                  </span>
                  <span className="w-32 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                    Type
                  </span>
                  <div className="w-20" />
                </div>
              )}

              {inputs.map((input, index) => (
                <div
                  key={index}
                  className="border border-[var(--color-border)] rounded-lg overflow-hidden"
                >
                  {/* Main row */}
                  <div className="flex items-center gap-3 px-3 py-2.5">
                    {/* Drag / reorder handle */}
                    <button
                      onClick={() => moveInput(index, index === 0 ? 1 : -1)}
                      className="p-0.5 hover:bg-[var(--color-surface-2)] rounded text-[var(--color-text-muted)] cursor-grab"
                      title="Reorder"
                    >
                      <GripVertical className="w-4 h-4" />
                    </button>

                    {/* Name */}
                    <input
                      type="text"
                      value={input.name}
                      onChange={(e) =>
                        updateInput(index, "name", e.target.value)
                      }
                      placeholder="parameter_name"
                      className="flex-1 h-9 px-3 text-sm border border-[var(--color-border)] rounded-md bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] placeholder:text-[var(--color-text-muted)/50]"
                      autoFocus={
                        expandedIndex === index && input.name === ""
                      }
                    />

                    {/* Type */}
                    <select
                      value={input.type}
                      onChange={(e) =>
                        updateInput(index, "type", e.target.value)
                      }
                      className="w-32 h-9 px-2 text-sm border border-[var(--color-border)] rounded-md bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                    >
                      {INPUT_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>

                    {/* Expand optional fields */}
                    <button
                      onClick={() =>
                        setExpandedIndex(
                          expandedIndex === index ? null : index
                        )
                      }
                      className="p-1.5 hover:bg-[var(--color-surface-2)] rounded text-[var(--color-text-muted)]"
                      title="Options"
                    >
                      {expandedIndex === index ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                    </button>

                    {/* Delete */}
                    <button
                      onClick={() => removeInput(index)}
                      className="p-1.5 hover:bg-red-500/20 rounded text-[var(--color-text-muted)] hover:text-red-400"
                      title="Remove"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Expanded options */}
                  {expandedIndex === index && (
                    <div className="px-3 pb-3 pt-1 border-t border-[var(--color-border)] bg-[var(--color-surface-2)/30] space-y-3">
                      <div className="flex items-center gap-3 pl-7">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={input.required}
                            onChange={(e) =>
                              updateInput(
                                index,
                                "required",
                                e.target.checked
                              )
                            }
                            className="w-4 h-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]"
                          />
                          <span className="text-sm">Required</span>
                        </label>
                      </div>
                      <div className="pl-7">
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                          Default value
                        </label>
                        <input
                          type="text"
                          value={
                            input.default_value != null
                              ? String(input.default_value)
                              : ""
                          }
                          onChange={(e) =>
                            updateInput(
                              index,
                              "default_value",
                              e.target.value || null
                            )
                          }
                          placeholder="None"
                          className="w-full h-9 px-3 text-sm border border-[var(--color-border)] rounded-md bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] placeholder:text-[var(--color-text-muted)/50]"
                        />
                      </div>
                      <div className="pl-7">
                        <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                          Description
                        </label>
                        <input
                          type="text"
                          value={input.description}
                          onChange={(e) =>
                            updateInput(
                              index,
                              "description",
                              e.target.value
                            )
                          }
                          placeholder="What this input is for"
                          className="w-full h-9 px-3 text-sm border border-[var(--color-border)] rounded-md bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] placeholder:text-[var(--color-text-muted)/50]"
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Add Input button */}
              <button
                onClick={addInput}
                className="flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg border border-dashed border-[var(--color-border)] hover:bg-[var(--color-surface-2)] hover:border-[var(--color-text-muted)] w-full justify-center transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Input
              </button>
            </div>
          )}
        </div>

        {/* Validation errors */}
        {validationErrors.length > 0 && (
          <div className="px-5 py-2.5 border-t border-[var(--color-border)]">
            {validationErrors.map((err, i) => (
              <p key={i} className="text-sm text-red-400">
                {err}
              </p>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-[var(--color-border)]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-md border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={
              !isDirty ||
              saveMutation.isPending ||
              validationErrors.length > 0
            }
            className="px-4 py-2 text-sm rounded-md bg-[var(--color-primary)] text-[#ffffff] hover:opacity-90 disabled:opacity-50 transition-colors"
          >
            {saveMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin inline mr-1.5" />
            ) : null}
            Save Inputs
          </button>
        </div>
      </div>
    </div>
  );
}
