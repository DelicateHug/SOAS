import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  NormalizationGroup,
  NormalizationRule,
  NormalizationTestResult,
  TransformType,
} from "@/types/api";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  FlaskConical,
  Save,
  AlertCircle,
  AlertTriangle,
  Info,
  User,
  Globe,
  Monitor,
  ShieldAlert,
  Clock,
  Tag,
  Database,
  Settings,
  HelpCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Icon mapping helper
// ---------------------------------------------------------------------------

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  user: User,
  globe: Globe,
  monitor: Monitor,
  "shield-alert": ShieldAlert,
  clock: Clock,
  tag: Tag,
  database: Database,
  settings: Settings,
};

function GroupIcon({ name, className }: { name?: string; className?: string }) {
  const Icon = (name && iconMap[name]) || HelpCircle;
  return <Icon className={className} />;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TRANSFORM_TYPES: TransformType[] = [
  "direct",
  "regex",
  "template",
  "static",
  "lookup",
  "lowercase",
  "uppercase",
];

const SAMPLE_PAYLOAD = JSON.stringify(
  {
    alert: {
      title: "Test Alert",
      severity: "high",
      src_ip: "192.168.1.100",
      dst_ip: "10.0.0.1",
      user: "admin",
    },
  },
  null,
  2
);

// ---------------------------------------------------------------------------
// Local rule type (may have temp ID before save)
// ---------------------------------------------------------------------------

interface LocalRule {
  id: string;
  group_id: string;
  source_path: string;
  target_field: string;
  transform_type: TransformType;
  transform_config: Record<string, unknown>;
  is_required: boolean;
  default_value?: unknown;
  display_order: number;
  is_enabled: boolean;
}

// ---------------------------------------------------------------------------
// Lookup mapping helper types
// ---------------------------------------------------------------------------

interface LookupMapping {
  source: string;
  mapped: string;
}

// ---------------------------------------------------------------------------
// Transform config sub-components
// ---------------------------------------------------------------------------

function TransformConfigEditor({
  rule,
  onChange,
}: {
  rule: LocalRule;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const config = rule.transform_config;

  switch (rule.transform_type) {
    case "direct":
    case "lowercase":
    case "uppercase":
      return (
        <p className="text-xs text-[hsl(var(--muted-foreground))] italic">
          No configuration needed.
        </p>
      );

    case "regex":
      return (
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
              Pattern
            </label>
            <input
              type="text"
              value={(config.pattern as string) ?? ""}
              onChange={(e) => onChange({ ...config, pattern: e.target.value })}
              placeholder="regex pattern"
              className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] font-mono"
            />
          </div>
          <div className="w-32">
            <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
              Capture group
            </label>
            <input
              type="number"
              min={0}
              value={(config.group as number) ?? 0}
              onChange={(e) =>
                onChange({ ...config, group: parseInt(e.target.value, 10) || 0 })
              }
              className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))]"
            />
          </div>
        </div>
      );

    case "template":
      return (
        <div>
          <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
            Template
          </label>
          <input
            type="text"
            value={(config.template as string) ?? ""}
            onChange={(e) => onChange({ ...config, template: e.target.value })}
            placeholder="e.g. {value} - enriched"
            className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] font-mono"
          />
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
            {"Use {value} as a placeholder for the source field value."}
          </p>
        </div>
      );

    case "static":
      return (
        <div>
          <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
            Static value
          </label>
          <input
            type="text"
            value={(config.value as string) ?? ""}
            onChange={(e) => onChange({ ...config, value: e.target.value })}
            placeholder="static value"
            className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))]"
          />
        </div>
      );

    case "lookup":
      return (
        <LookupConfigEditor
          config={config}
          onChange={onChange}
        />
      );

    default:
      return null;
  }
}

function LookupConfigEditor({
  config,
  onChange,
}: {
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}) {
  const mappings: LookupMapping[] = Array.isArray(config.mappings)
    ? (config.mappings as LookupMapping[])
    : [];
  const defaultValue = (config.default as string) ?? "";

  const updateMappings = (updated: LookupMapping[]) => {
    onChange({ ...config, mappings: updated });
  };

  const addMapping = () => {
    updateMappings([...mappings, { source: "", mapped: "" }]);
  };

  const removeMapping = (index: number) => {
    updateMappings(mappings.filter((_, i) => i !== index));
  };

  const updateMapping = (index: number, field: "source" | "mapped", value: string) => {
    const updated = mappings.map((m, i) =>
      i === index ? { ...m, [field]: value } : m
    );
    updateMappings(updated);
  };

  return (
    <div className="space-y-3">
      <div className="border border-[hsl(var(--border))] rounded-md overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[hsl(var(--accent))]">
            <tr>
              <th className="text-left px-3 py-1.5 text-xs font-medium">Source Value</th>
              <th className="text-left px-3 py-1.5 text-xs font-medium">Mapped Value</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[hsl(var(--border))]">
            {mappings.map((m, i) => (
              <tr key={i}>
                <td className="px-2 py-1.5">
                  <input
                    type="text"
                    value={m.source}
                    onChange={(e) => updateMapping(i, "source", e.target.value)}
                    placeholder="source"
                    className="w-full px-2 py-1 text-xs rounded border border-[hsl(var(--input))] bg-[hsl(var(--background))]"
                  />
                </td>
                <td className="px-2 py-1.5">
                  <input
                    type="text"
                    value={m.mapped}
                    onChange={(e) => updateMapping(i, "mapped", e.target.value)}
                    placeholder="mapped"
                    className="w-full px-2 py-1 text-xs rounded border border-[hsl(var(--input))] bg-[hsl(var(--background))]"
                  />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button
                    onClick={() => removeMapping(i)}
                    className="p-0.5 rounded hover:bg-red-500/20 text-red-400 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </td>
              </tr>
            ))}
            {mappings.length === 0 && (
              <tr>
                <td colSpan={3} className="text-center py-2 text-xs text-[hsl(var(--muted-foreground))]">
                  No mappings yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <button
        onClick={addMapping}
        className="flex items-center gap-1 text-xs text-[hsl(var(--primary))] hover:underline"
      >
        <Plus className="w-3 h-3" /> Add Mapping
      </button>
      <div>
        <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">
          Default (when no mapping matches)
        </label>
        <input
          type="text"
          value={defaultValue}
          onChange={(e) => onChange({ ...config, default: e.target.value })}
          placeholder="default value"
          className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))]"
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rule row component
// ---------------------------------------------------------------------------

function RuleRow({
  rule,
  isExpanded,
  onToggleExpand,
  onUpdate,
  onDelete,
}: {
  rule: LocalRule;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onUpdate: (updated: LocalRule) => void;
  onDelete: () => void;
}) {
  const updateField = <K extends keyof LocalRule>(field: K, value: LocalRule[K]) => {
    onUpdate({ ...rule, [field]: value });
  };

  return (
    <div className="border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--background))]">
      {/* Compact row */}
      <div className="flex items-center gap-2 px-3 py-2">
        <input
          type="text"
          value={rule.source_path}
          onChange={(e) => updateField("source_path", e.target.value)}
          placeholder="e.g. data.alert.src_ip"
          className="flex-1 min-w-0 px-2 py-1.5 text-sm rounded border border-[hsl(var(--input))] bg-[hsl(var(--background))] font-mono"
        />
        <ArrowRight className="w-4 h-4 shrink-0 text-[hsl(var(--muted-foreground))]" />
        <input
          type="text"
          value={rule.target_field}
          onChange={(e) => updateField("target_field", e.target.value)}
          placeholder="e.g. source_ip"
          className="flex-1 min-w-0 px-2 py-1.5 text-sm rounded border border-[hsl(var(--input))] bg-[hsl(var(--background))] font-mono"
        />
        <select
          value={rule.transform_type}
          onChange={(e) => {
            const newType = e.target.value as TransformType;
            onUpdate({
              ...rule,
              transform_type: newType,
              transform_config:
                newType === rule.transform_type ? rule.transform_config : {},
            });
          }}
          className="px-2 py-1.5 text-sm rounded border border-[hsl(var(--input))] bg-[hsl(var(--background))] shrink-0"
        >
          {TRANSFORM_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        {/* Enabled toggle */}
        <button
          onClick={() => updateField("is_enabled", !rule.is_enabled)}
          className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
            rule.is_enabled
              ? "bg-[hsl(var(--primary))]"
              : "bg-[hsl(var(--muted))]"
          }`}
          title={rule.is_enabled ? "Enabled" : "Disabled"}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
              rule.is_enabled ? "translate-x-4" : "translate-x-0.5"
            }`}
          />
        </button>

        {/* Configure / expand button */}
        <button
          onClick={onToggleExpand}
          className="px-2 py-1 text-xs rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))] transition-colors shrink-0"
        >
          {isExpanded ? "Close" : "Configure"}
        </button>

        {/* Delete */}
        <button
          onClick={onDelete}
          className="p-1 rounded hover:bg-red-500/20 text-red-400 transition-colors shrink-0"
          title="Delete rule"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Expanded details panel */}
      {isExpanded && (
        <div className="border-t border-[hsl(var(--border))] px-4 py-3 space-y-3 bg-[hsl(var(--muted))]/30">
          {/* Transform config */}
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase mb-2">
              Transform Configuration
            </p>
            <TransformConfigEditor
              rule={rule}
              onChange={(config) => updateField("transform_config", config)}
            />
          </div>

          {/* Required + Default value row */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={rule.is_required}
                onChange={(e) => updateField("is_required", e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Required</span>
            </label>
            <div className="flex-1">
              <input
                type="text"
                value={
                  rule.default_value !== undefined && rule.default_value !== null
                    ? String(rule.default_value)
                    : ""
                }
                onChange={(e) =>
                  updateField(
                    "default_value",
                    e.target.value === "" ? undefined : e.target.value
                  )
                }
                placeholder="fallback value if source field missing"
                className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))]"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Test panel component
// ---------------------------------------------------------------------------

function TestPanel({
  onClose,
}: {
  onClose: () => void;
}) {
  const [payload, setPayload] = useState(SAMPLE_PAYLOAD);
  const [result, setResult] = useState<NormalizationTestResult | null>(null);

  const testMutation = useMutation({
    mutationFn: () => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(payload);
      } catch {
        throw { error: "Invalid JSON payload", status_code: 400 };
      }
      return api.post<NormalizationTestResult>("/normalization/test", {
        raw_payload: parsed,
      });
    },
    onSuccess: (data) => setResult(data),
    onError: () => {
      setResult({
        normalized: {},
        errors: ["Failed to run test. Check your JSON payload."],
        warnings: [],
      });
    },
  });

  return (
    <div className="border border-[hsl(var(--border))] rounded-lg h-full flex flex-col bg-[hsl(var(--background))]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
        <span className="text-sm font-semibold">Test Panel</span>
        <button
          onClick={onClose}
          className="text-xs px-2 py-1 rounded border border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))] transition-colors"
        >
          Close
        </button>
      </div>

      {/* Payload input */}
      <div className="p-4 flex-1 flex flex-col gap-3 overflow-y-auto">
        <div>
          <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1 block">
            Test Payload
          </label>
          <textarea
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            rows={10}
            placeholder={SAMPLE_PAYLOAD}
            className="w-full px-3 py-2 text-sm rounded-md border border-[hsl(var(--input))] bg-[hsl(var(--background))] font-mono resize-y"
          />
        </div>

        <button
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
          className="flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50 transition-colors"
        >
          <FlaskConical className="w-4 h-4" />
          {testMutation.isPending ? "Running..." : "Run Test"}
        </button>

        {/* Results */}
        {result && (
          <div className="space-y-3">
            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <AlertCircle className="w-4 h-4 text-red-400" />
                  <span className="text-sm font-medium text-red-400">
                    Errors
                  </span>
                </div>
                <ul className="text-xs text-red-300 space-y-0.5 ml-6 list-disc">
                  {result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div className="rounded-md border border-yellow-500/30 bg-yellow-500/10 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                  <span className="text-sm font-medium text-yellow-400">
                    Warnings
                  </span>
                </div>
                <ul className="text-xs text-yellow-300 space-y-0.5 ml-6 list-disc">
                  {result.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Normalized output */}
            <div>
              <label className="text-xs font-medium text-[hsl(var(--muted-foreground))] mb-1 block">
                Normalized Output
              </label>
              <pre className="text-xs font-mono p-3 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))] overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                {JSON.stringify(result.normalized, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {!result && (
          <div className="flex items-center gap-2 text-xs text-[hsl(var(--muted-foreground))] p-3 rounded-md border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/50">
            <Info className="w-4 h-4 shrink-0" />
            <span>
              Paste a sample payload and click "Run Test" to see the
              normalized output.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export function NormalizationEditorPage() {
  // UI state
  const [showTestPanel, setShowTestPanel] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [expandedRuleId, setExpandedRuleId] = useState<string | null>(null);

  // Local rules state (editable clone of server data)
  const [localRules, setLocalRules] = useState<LocalRule[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // ---------------------------------------------------------------------------
  // Queries
  // ---------------------------------------------------------------------------

  const { data: groups, isLoading: groupsLoading } = useQuery({
    queryKey: ["normalization-groups"],
    queryFn: () => api.get<NormalizationGroup[]>("/normalization/groups"),
  });

  const { data: serverRules, isLoading: rulesLoading } = useQuery({
    queryKey: ["normalization-rules"],
    queryFn: () => api.get<NormalizationRule[]>("/normalization/rules"),
  });

  // Initialize local rules from server data
  useEffect(() => {
    if (serverRules && !initialized) {
      setLocalRules(
        serverRules.map((r) => ({
          id: r.id,
          group_id: r.group_id,
          source_path: r.source_path,
          target_field: r.target_field,
          transform_type: r.transform_type,
          transform_config: { ...r.transform_config },
          is_required: r.is_required,
          default_value: r.default_value,
          display_order: r.display_order,
          is_enabled: r.is_enabled,
        }))
      );
      setInitialized(true);
    }
  }, [serverRules, initialized]);

  // ---------------------------------------------------------------------------
  // Save mutation
  // ---------------------------------------------------------------------------

  const saveMutation = useMutation({
    mutationFn: () =>
      api.request<NormalizationRule[]>("/normalization/rules/bulk", {
        method: "PUT",
        body: JSON.stringify({
          rules: localRules,
        }),
      }),
    onSuccess: (savedRules) => {
      // Update local rules with server-assigned IDs
      setLocalRules(
        savedRules.map((r) => ({
          id: r.id,
          group_id: r.group_id,
          source_path: r.source_path,
          target_field: r.target_field,
          transform_type: r.transform_type,
          transform_config: { ...r.transform_config },
          is_required: r.is_required,
          default_value: r.default_value,
          display_order: r.display_order,
          is_enabled: r.is_enabled,
        }))
      );
      setIsDirty(false);
    },
  });

  // ---------------------------------------------------------------------------
  // Rule helpers
  // ---------------------------------------------------------------------------

  const rulesForGroup = useCallback(
    (groupId: string) =>
      localRules
        .filter((r) => r.group_id === groupId)
        .sort((a, b) => a.display_order - b.display_order),
    [localRules]
  );

  const toggleGroup = (groupId: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  };

  const addRule = (groupId: string) => {
    const groupRules = rulesForGroup(groupId);
    const maxOrder =
      groupRules.length > 0
        ? Math.max(...groupRules.map((r) => r.display_order))
        : -1;

    const newRule: LocalRule = {
      id: crypto.randomUUID(),
      group_id: groupId,
      source_path: "",
      target_field: "",
      transform_type: "direct",
      transform_config: {},
      is_required: false,
      default_value: undefined,
      display_order: maxOrder + 1,
      is_enabled: true,
    };

    setLocalRules((prev) => [...prev, newRule]);
    setIsDirty(true);

    // Ensure group is expanded
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      next.add(groupId);
      return next;
    });
  };

  const updateRule = (updated: LocalRule) => {
    setLocalRules((prev) =>
      prev.map((r) => (r.id === updated.id ? updated : r))
    );
    setIsDirty(true);
  };

  const deleteRule = (ruleId: string) => {
    setLocalRules((prev) => prev.filter((r) => r.id !== ruleId));
    setIsDirty(true);
    if (expandedRuleId === ruleId) {
      setExpandedRuleId(null);
    }
  };

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------

  const isLoading = groupsLoading || rulesLoading;
  const sortedGroups = (groups ?? []).sort(
    (a, b) => a.display_order - b.display_order
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="h-full flex flex-col">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">Field Normalization</h1>
          {isDirty && (
            <span className="px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-xs font-medium">
              Unsaved changes
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowTestPanel((v) => !v)}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md border transition-colors ${
              showTestPanel
                ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] border-transparent"
                : "border-[hsl(var(--border))] hover:bg-[hsl(var(--accent))]"
            }`}
          >
            <FlaskConical className="w-4 h-4" />
            Test
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !isDirty}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-md bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50 transition-colors"
          >
            <Save className="w-4 h-4" />
            {saveMutation.isPending ? "Saving..." : "Save All"}
          </button>
        </div>
      </div>

      {/* Save error */}
      {saveMutation.isError && (
        <div className="mb-4 rounded-md border border-red-500/30 bg-red-500/10 p-3 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-400">
            Failed to save rules. Please try again.
          </span>
        </div>
      )}

      {/* Save success */}
      {saveMutation.isSuccess && !isDirty && (
        <div className="mb-4 rounded-md border border-green-500/30 bg-green-500/10 p-3 flex items-center gap-2">
          <Info className="w-4 h-4 text-green-400 shrink-0" />
          <span className="text-sm text-green-400">
            Rules saved successfully.
          </span>
        </div>
      )}

      {/* Main content */}
      {isLoading ? (
        <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
          Loading...
        </div>
      ) : (
        <div className={`flex gap-4 flex-1 min-h-0 ${showTestPanel ? "" : ""}`}>
          {/* Rule editor */}
          <div
            className={`flex-1 overflow-y-auto space-y-3 ${
              showTestPanel ? "w-[60%]" : "w-full"
            }`}
            style={showTestPanel ? { flex: "0 0 60%" } : undefined}
          >
            {sortedGroups.length === 0 ? (
              <div className="text-center py-12 text-[hsl(var(--muted-foreground))]">
                <p>No normalization groups defined.</p>
                <p className="text-sm mt-1">
                  Create normalization groups first to organize your rules.
                </p>
              </div>
            ) : (
              sortedGroups.map((group) => {
                const groupRules = rulesForGroup(group.id);
                const isExpanded = expandedGroups.has(group.id);

                return (
                  <div
                    key={group.id}
                    className="border border-[hsl(var(--border))] rounded-lg overflow-hidden"
                  >
                    {/* Group header */}
                    <button
                      onClick={() => toggleGroup(group.id)}
                      className="w-full px-4 py-3 flex items-center justify-between bg-[hsl(var(--muted))] hover:bg-[hsl(var(--accent))] transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <GroupIcon
                          name={group.icon}
                          className="w-4 h-4 text-[hsl(var(--muted-foreground))]"
                        />
                        <div className="text-left">
                          <p className="font-medium text-sm">
                            {group.display_name}
                          </p>
                          {group.description && (
                            <p className="text-xs text-[hsl(var(--muted-foreground))]">
                              {group.description}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded-full bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] text-xs">
                          {groupRules.length}{" "}
                          {groupRules.length === 1 ? "rule" : "rules"}
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
                        )}
                      </div>
                    </button>

                    {/* Group body */}
                    {isExpanded && (
                      <div className="border-t border-[hsl(var(--border))] p-4 space-y-2">
                        {groupRules.length === 0 ? (
                          <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-4">
                            No rules in this group. Add one below.
                          </p>
                        ) : (
                          groupRules.map((rule) => (
                            <RuleRow
                              key={rule.id}
                              rule={rule}
                              isExpanded={expandedRuleId === rule.id}
                              onToggleExpand={() =>
                                setExpandedRuleId(
                                  expandedRuleId === rule.id ? null : rule.id
                                )
                              }
                              onUpdate={updateRule}
                              onDelete={() => deleteRule(rule.id)}
                            />
                          ))
                        )}

                        {/* Add rule button */}
                        <button
                          onClick={() => addRule(group.id)}
                          className="flex items-center gap-1.5 text-sm text-[hsl(var(--primary))] hover:underline mt-2"
                        >
                          <Plus className="w-3.5 h-3.5" /> Add Rule
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Test panel */}
          {showTestPanel && (
            <div className="overflow-y-auto" style={{ flex: "0 0 40%" }}>
              <TestPanel
                onClose={() => setShowTestPanel(false)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
