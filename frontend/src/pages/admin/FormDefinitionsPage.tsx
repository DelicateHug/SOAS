import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, Trash2, Edit2, X, ToggleLeft, ToggleRight, GripVertical, ChevronUp, ChevronDown } from "lucide-react";
import type { FormDefinition, FormField, FormFieldType, PaginatedResponse } from "@/types/api";

const FIELD_TYPES: { value: FormFieldType; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "textarea", label: "Textarea" },
  { value: "number", label: "Number" },
  { value: "select", label: "Select" },
  { value: "checkbox", label: "Checkbox" },
  { value: "date", label: "Date" },
];

const emptyField = (): FormField => ({
  key: "",
  label: "",
  type: "text",
  required: false,
  options: [],
  placeholder: "",
  help_text: "",
});

export function FormDefinitionsPage() {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingDefn, setEditingDefn] = useState<FormDefinition | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formIsActive, setFormIsActive] = useState(true);
  const [formFields, setFormFields] = useState<FormField[]>([emptyField()]);

  const { data: response, isLoading } = useQuery({
    queryKey: ["form-definitions"],
    queryFn: () => api.get<PaginatedResponse<FormDefinition>>("/form-definitions?per_page=100"),
  });

  const definitions = response?.data ?? [];

  const createDefn = useMutation({
    mutationFn: () =>
      api.post("/form-definitions", {
        name: formName,
        description: formDescription || null,
        fields: formFields.filter((f) => f.key && f.label),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-definitions"] });
      closeModal();
    },
  });

  const updateDefn = useMutation({
    mutationFn: () => {
      if (!editingDefn) return Promise.reject("No definition");
      return api.patch(`/form-definitions/${editingDefn.id}`, {
        name: formName,
        description: formDescription || null,
        fields: formFields.filter((f) => f.key && f.label),
        is_active: formIsActive,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-definitions"] });
      closeModal();
    },
  });

  const deleteDefn = useMutation({
    mutationFn: (id: string) => api.delete(`/form-definitions/${id}`),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["form-definitions"] }),
    onError: (error: { detail?: string }) => {
      alert(error.detail || "Cannot delete form definition with existing submissions.");
    },
  });

  const toggleActive = useMutation({
    mutationFn: (d: FormDefinition) =>
      api.patch(`/form-definitions/${d.id}`, { is_active: !d.is_active }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["form-definitions"] }),
  });

  const closeModal = () => {
    setShowModal(false);
    setEditingDefn(null);
    resetForm();
  };

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormIsActive(true);
    setFormFields([emptyField()]);
  };

  const openEdit = (d: FormDefinition) => {
    setEditingDefn(d);
    setFormName(d.name);
    setFormDescription(d.description || "");
    setFormIsActive(d.is_active);
    setFormFields(d.fields.length > 0 ? d.fields.map((f) => ({ ...f })) : [emptyField()]);
    setShowModal(true);
  };

  const updateField = (index: number, updates: Partial<FormField>) => {
    setFormFields((prev) =>
      prev.map((f, i) => (i === index ? { ...f, ...updates } : f))
    );
  };

  const removeField = (index: number) => {
    setFormFields((prev) => prev.filter((_, i) => i !== index));
  };

  const moveField = (index: number, direction: -1 | 1) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= formFields.length) return;
    setFormFields((prev) => {
      const next = [...prev];
      const temp = next[index]!;
      next[index] = next[newIndex]!;
      next[newIndex] = temp;
      return next;
    });
  };

  const validFields = formFields.filter((f) => f.key && f.label);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Form Definitions</h1>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            Create reusable form templates that can be filled out during incident response.
          </p>
        </div>
        <button
          onClick={() => {
            resetForm();
            setShowModal(true);
          }}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Create Form
        </button>
      </div>

      {isLoading ? (
        <p className="text-[hsl(var(--muted-foreground))]">Loading...</p>
      ) : definitions.length === 0 ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          <p>No form definitions yet.</p>
          <p className="text-sm mt-1">Create one to start collecting structured data in incidents.</p>
        </div>
      ) : (
        <div className="border border-[hsl(var(--border))] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[hsl(var(--accent))]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-left px-4 py-2 font-medium">Description</th>
                <th className="text-center px-4 py-2 font-medium">Fields</th>
                <th className="text-center px-4 py-2 font-medium">Active</th>
                <th className="text-right px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]">
              {definitions.map((d) => (
                <tr key={d.id} className="hover:bg-[hsl(var(--accent))]/50">
                  <td className="px-4 py-2 font-medium">{d.name}</td>
                  <td className="px-4 py-2 text-[hsl(var(--muted-foreground))] max-w-[300px] truncate">
                    {d.description || "-"}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span className="text-xs px-2 py-0.5 rounded bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                      {d.fields.length}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-center">
                    <button
                      onClick={() => toggleActive.mutate(d)}
                      className="inline-flex items-center"
                      title={d.is_active ? "Active" : "Inactive"}
                    >
                      {d.is_active ? (
                        <ToggleRight className="w-5 h-5 text-green-500" />
                      ) : (
                        <ToggleLeft className="w-5 h-5 text-[hsl(var(--muted-foreground))]" />
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEdit(d)}
                        className="p-1 rounded hover:bg-[hsl(var(--accent))] transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete form "${d.name}"?`))
                            deleteDefn.mutate(d.id);
                        }}
                        className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-xl w-[700px] max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))]">
              <h3 className="font-semibold text-sm">
                {editingDefn ? "Edit Form Definition" : "Create Form Definition"}
              </h3>
              <button onClick={closeModal} className="p-1 rounded hover:bg-[hsl(var(--accent))]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-4 overflow-y-auto flex-1">
              {/* Name */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. Containment Checklist"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>

              {/* Description */}
              <div>
                <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">Description</label>
                <input
                  type="text"
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="What this form is used for"
                  className="w-full px-3 py-2 text-sm rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                />
              </div>

              {/* Active toggle */}
              {editingDefn && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formIsActive}
                    onChange={(e) => setFormIsActive(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Active (available for use in incidents)</span>
                </label>
              )}

              {/* Fields Builder */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs text-[hsl(var(--muted-foreground))]">Fields</label>
                  <button
                    onClick={() => setFormFields((prev) => [...prev, emptyField()])}
                    className="text-xs px-2 py-1 rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
                  >
                    + Add Field
                  </button>
                </div>

                <div className="space-y-2">
                  {formFields.map((field, idx) => (
                    <div
                      key={idx}
                      className="rounded border border-[hsl(var(--border))] p-3 space-y-2"
                    >
                      <div className="flex items-center gap-2">
                        <GripVertical className="w-3 h-3 text-[hsl(var(--muted-foreground))] shrink-0" />
                        <span className="text-xs text-[hsl(var(--muted-foreground))] w-6">#{idx + 1}</span>
                        <div className="flex gap-1 ml-auto">
                          <button
                            onClick={() => moveField(idx, -1)}
                            disabled={idx === 0}
                            className="p-0.5 rounded hover:bg-[hsl(var(--accent))] disabled:opacity-30"
                          >
                            <ChevronUp className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => moveField(idx, 1)}
                            disabled={idx === formFields.length - 1}
                            className="p-0.5 rounded hover:bg-[hsl(var(--accent))] disabled:opacity-30"
                          >
                            <ChevronDown className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => removeField(idx)}
                            disabled={formFields.length <= 1}
                            className="p-0.5 rounded hover:bg-red-500/20 text-red-400 disabled:opacity-30"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="text-[10px] text-[hsl(var(--muted-foreground))] mb-0.5 block">Key</label>
                          <input
                            type="text"
                            value={field.key}
                            onChange={(e) =>
                              updateField(idx, { key: e.target.value.replace(/\s/g, "_").toLowerCase() })
                            }
                            placeholder="field_key"
                            className="w-full px-2 py-1.5 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] font-mono"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-[hsl(var(--muted-foreground))] mb-0.5 block">Label</label>
                          <input
                            type="text"
                            value={field.label}
                            onChange={(e) => updateField(idx, { label: e.target.value })}
                            placeholder="Field Label"
                            className="w-full px-2 py-1.5 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-[hsl(var(--muted-foreground))] mb-0.5 block">Type</label>
                          <select
                            value={field.type}
                            onChange={(e) => updateField(idx, { type: e.target.value as FormFieldType })}
                            className="w-full px-2 py-1.5 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                          >
                            {FIELD_TYPES.map((t) => (
                              <option key={t.value} value={t.value}>
                                {t.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={field.required}
                            onChange={(e) => updateField(idx, { required: e.target.checked })}
                            className="rounded"
                          />
                          <span className="text-xs">Required</span>
                        </label>
                        <div className="flex-1">
                          <input
                            type="text"
                            value={field.placeholder || ""}
                            onChange={(e) => updateField(idx, { placeholder: e.target.value })}
                            placeholder="Placeholder text"
                            className="w-full px-2 py-1 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                          />
                        </div>
                      </div>

                      {field.type === "select" && (
                        <div>
                          <label className="text-[10px] text-[hsl(var(--muted-foreground))] mb-0.5 block">
                            Options (comma-separated)
                          </label>
                          <input
                            type="text"
                            value={field.options.join(", ")}
                            onChange={(e) =>
                              updateField(idx, {
                                options: e.target.value.split(",").map((o) => o.trim()).filter(Boolean),
                              })
                            }
                            placeholder="Option 1, Option 2, Option 3"
                            className="w-full px-2 py-1.5 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))]"
                          />
                        </div>
                      )}

                      <div>
                        <input
                          type="text"
                          value={field.help_text || ""}
                          onChange={(e) => updateField(idx, { help_text: e.target.value })}
                          placeholder="Help text (optional)"
                          className="w-full px-2 py-1 text-xs rounded border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-[hsl(var(--muted-foreground))]"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-4 py-3 border-t border-[hsl(var(--border))]">
              <button
                onClick={closeModal}
                className="px-3 py-1.5 text-sm rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
              >
                Cancel
              </button>
              <button
                onClick={() => (editingDefn ? updateDefn.mutate() : createDefn.mutate())}
                disabled={
                  !formName.trim() ||
                  validFields.length === 0 ||
                  createDefn.isPending ||
                  updateDefn.isPending
                }
                className="px-3 py-1.5 text-sm rounded bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
              >
                {editingDefn ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
