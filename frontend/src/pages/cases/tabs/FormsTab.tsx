import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { SectionHeader } from "@/components/ui/SectionHeader";
import type {
  FormDefinition,
  FormField,
  CaseFormSubmission,
  PaginatedResponse,
} from "@/types/api";

interface Props {
  caseId: string;
}

export function FormsTab({ caseId }: Props) {
  const queryClient = useQueryClient();
  const [showSubmitForm, setShowSubmitForm] = useState(false);
  const [selectedFormId, setSelectedFormId] = useState<string>("");
  const [formData, setFormData] = useState<Record<string, unknown>>({});

  const { data: submissions } = useQuery({
    queryKey: ["case-form-submissions", caseId],
    queryFn: () =>
      api.get<CaseFormSubmission[]>(`/cases/${caseId}/form-submissions`),
  });

  const { data: definitionsResponse } = useQuery({
    queryKey: ["form-definitions-active"],
    queryFn: () =>
      api.get<PaginatedResponse<FormDefinition>>(
        "/form-definitions?active_only=true&per_page=100"
      ),
    enabled: showSubmitForm,
  });

  const definitions = definitionsResponse?.data ?? [];
  const selectedDefinition = definitions.find((d) => d.id === selectedFormId);

  const submitForm = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/form-submissions`, {
        form_definition_id: selectedFormId,
        data: formData,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["case-form-submissions", caseId],
      });
      queryClient.invalidateQueries({
        queryKey: ["case-timeline", caseId],
      });
      setShowSubmitForm(false);
      setSelectedFormId("");
      setFormData({});
    },
  });

  const deleteSubmission = useMutation({
    mutationFn: (submissionId: string) =>
      api.delete(`/cases/${caseId}/form-submissions/${submissionId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["case-form-submissions", caseId],
      });
    },
  });

  const toggleEvidence = useMutation({
    mutationFn: (submissionId: string) =>
      api.post<CaseFormSubmission>(
        `/cases/${caseId}/form-submissions/${submissionId}/evidence`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["case-form-submissions", caseId],
      });
      queryClient.invalidateQueries({
        queryKey: ["case-timeline", caseId],
      });
    },
  });

  const updateFieldValue = (key: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const handleSelectForm = (formId: string) => {
    setSelectedFormId(formId);
    setFormData({});
  };

  const renderField = (field: FormField) => {
    const value = formData[field.key];
    const baseClasses =
      "w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm bg-transparent";

    switch (field.type) {
      case "text":
        return (
          <input
            type="text"
            value={(value as string) ?? ""}
            onChange={(e) => updateFieldValue(field.key, e.target.value)}
            placeholder={field.placeholder || ""}
            className={baseClasses}
          />
        );
      case "textarea":
        return (
          <textarea
            value={(value as string) ?? ""}
            onChange={(e) => updateFieldValue(field.key, e.target.value)}
            placeholder={field.placeholder || ""}
            className={`${baseClasses} min-h-20 resize-y`}
          />
        );
      case "number":
        return (
          <input
            type="number"
            value={(value as number) ?? ""}
            onChange={(e) =>
              updateFieldValue(
                field.key,
                e.target.value === "" ? "" : Number(e.target.value)
              )
            }
            placeholder={field.placeholder || ""}
            className={baseClasses}
          />
        );
      case "select":
        return (
          <select
            value={(value as string) ?? ""}
            onChange={(e) => updateFieldValue(field.key, e.target.value)}
            className={baseClasses}
          >
            <option value="">Select...</option>
            {field.options.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        );
      case "checkbox":
        return (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={!!value}
              onChange={(e) => updateFieldValue(field.key, e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-[hsl(var(--muted-foreground))]">
              {field.placeholder || "Yes"}
            </span>
          </label>
        );
      case "date":
        return (
          <input
            type="date"
            value={(value as string) ?? ""}
            onChange={(e) => updateFieldValue(field.key, e.target.value)}
            className={baseClasses}
          />
        );
      default:
        return (
          <input
            type="text"
            value={(value as string) ?? ""}
            onChange={(e) => updateFieldValue(field.key, e.target.value)}
            className={baseClasses}
          />
        );
    }
  };

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Forms"
        action={
          !showSubmitForm ? (
            <button
              onClick={() => setShowSubmitForm(true)}
              className="px-3 py-1.5 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-xs font-medium"
            >
              Submit Form
            </button>
          ) : undefined
        }
      />

      {showSubmitForm && (
        <div className="rounded-lg border border-[hsl(var(--border))] p-4 space-y-4">
          <div>
            <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
              Select Form
            </label>
            <select
              value={selectedFormId}
              onChange={(e) => handleSelectForm(e.target.value)}
              className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md text-sm bg-transparent"
            >
              <option value="">Choose a form...</option>
              {definitions.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                  {d.description ? ` - ${d.description}` : ""}
                </option>
              ))}
            </select>
          </div>

          {selectedDefinition && (
            <div className="space-y-3">
              {selectedDefinition.fields.map((field) => (
                <div key={field.key}>
                  <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
                    {field.label}
                    {field.required && (
                      <span className="text-red-400 ml-0.5">*</span>
                    )}
                  </label>
                  {renderField(field)}
                  {field.help_text && (
                    <p className="text-[10px] text-[hsl(var(--muted-foreground))] mt-0.5">
                      {field.help_text}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={() => selectedFormId && submitForm.mutate()}
              disabled={!selectedFormId || submitForm.isPending}
              className="px-4 py-1.5 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md text-sm disabled:opacity-50"
            >
              {submitForm.isPending ? "Submitting..." : "Submit"}
            </button>
            <button
              onClick={() => {
                setShowSubmitForm(false);
                setSelectedFormId("");
                setFormData({});
              }}
              className="px-4 py-1.5 border border-[hsl(var(--border))] rounded-md text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {submissions?.map((sub) => (
          <div
            key={sub.id}
            className="rounded-lg border border-[hsl(var(--border))] p-4"
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-medium">
                {sub.form_definition.name}
              </span>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                &middot;
              </span>
              <UserAvatar
                displayName={sub.submitted_by.display_name}
                size="sm"
              />
              <span className="text-xs font-medium">
                {sub.submitted_by.display_name}
              </span>
              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                {formatDate(sub.created_at)}
              </span>
              {sub.is_evidence && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                  evidence
                </span>
              )}
              <div className="ml-auto flex gap-1">
                <button
                  onClick={() => toggleEvidence.mutate(sub.id)}
                  className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                    sub.is_evidence
                      ? "border-amber-500 text-amber-400"
                      : "border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:text-amber-400"
                  }`}
                >
                  {sub.is_evidence ? "Unmark" : "Evidence"}
                </button>
                <button
                  onClick={() => {
                    if (confirm("Delete this submission?"))
                      deleteSubmission.mutate(sub.id);
                  }}
                  className="text-xs px-2 py-0.5 rounded border border-[hsl(var(--border))] text-red-400 hover:text-red-300"
                >
                  Delete
                </button>
              </div>
            </div>

            <div className="rounded border border-[hsl(var(--border))] overflow-hidden">
              <table className="w-full text-xs">
                <tbody className="divide-y divide-[hsl(var(--border))]">
                  {Object.entries(sub.data).map(([key, value]) => (
                    <tr key={key}>
                      <td className="px-3 py-1.5 font-medium text-[hsl(var(--muted-foreground))] w-1/3">
                        {key}
                      </td>
                      <td className="px-3 py-1.5 font-mono">
                        {formatValue(value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
        {(!submissions || submissions.length === 0) && !showSubmitForm && (
          <div className="py-8 text-center text-[hsl(var(--muted-foreground))]">
            No form submissions yet
          </div>
        )}
      </div>
    </div>
  );
}
