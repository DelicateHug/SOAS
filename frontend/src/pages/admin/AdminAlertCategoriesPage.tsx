import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Tag } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

interface Rule {
  id: string;
  field: string;
  pattern: string;
  case_sensitive: boolean;
  is_enabled: boolean;
  sort_order: number;
}

interface Category {
  id: string;
  key: string;
  label: string;
  description: string | null;
  default_severity: string | null;
  default_priority: string | null;
  is_system: boolean;
  sort_order: number;
  rules: Rule[];
}

export function AdminAlertCategoriesPage() {
  const qc = useQueryClient();
  const { data: cats = [], isLoading } = useQuery({
    queryKey: ["alert-categories"],
    queryFn: () => api.get<Category[]>("/alert-categories"),
  });

  const addRule = useMutation({
    mutationFn: ({ catId, rule }: { catId: string; rule: { field: string; pattern: string } }) =>
      api.post(`/alert-categories/${catId}/rules`, rule),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-categories"] }),
  });

  const deleteRule = useMutation({
    mutationFn: (ruleId: string) => api.delete(`/alert-categories/rules/${ruleId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert-categories"] }),
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Alert Categories</h1>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          Categories drive auto-classification, dedup grouping, and per-category default response policies.
        </p>
      </div>

      {isLoading ? (
        <div className="text-sm text-[var(--color-text-muted)]">Loading…</div>
      ) : (
        cats.map((cat) => (
          <CategoryRow
            key={cat.id}
            cat={cat}
            onAddRule={(field, pattern) => addRule.mutate({ catId: cat.id, rule: { field, pattern } })}
            onDeleteRule={(id) => deleteRule.mutate(id)}
          />
        ))
      )}
    </div>
  );
}

function CategoryRow({
  cat,
  onAddRule,
  onDeleteRule,
}: {
  cat: Category;
  onAddRule: (field: string, pattern: string) => void;
  onDeleteRule: (id: string) => void;
}) {
  const [field, setField] = useState("title");
  const [pattern, setPattern] = useState("");

  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Tag size={14} className="text-[var(--color-text-muted)]" />
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">
                {cat.label} <span className="text-[var(--color-text-muted)] font-mono text-xs">({cat.key})</span>
              </div>
              {cat.description && (
                <div className="text-xs text-[var(--color-text-muted)]">{cat.description}</div>
              )}
            </div>
          </div>
          {cat.is_system && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] uppercase">
              system
            </span>
          )}
        </div>
        <div className="space-y-1.5">
          {cat.rules.map((r) => (
            <div key={r.id} className="flex items-center gap-2 text-xs font-mono px-2 py-1 bg-[var(--color-surface-2)] rounded">
              <span className="text-[var(--color-text-muted)]">{r.field}</span>
              <span className="text-[var(--color-text-muted)]">⟶</span>
              <span className="flex-1 truncate text-[var(--color-text)]">{r.pattern}</span>
              {!r.case_sensitive && (
                <span className="text-[10px] text-[var(--color-text-muted)]">i</span>
              )}
              <button
                onClick={() => onDeleteRule(r.id)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
              >
                <Trash2 size={11} />
              </button>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 mt-3">
          <input
            value={field}
            onChange={(e) => setField(e.target.value)}
            placeholder="field"
            className="w-32 px-2 py-1 text-xs font-mono border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
          />
          <input
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="regex pattern"
            className="flex-1 px-2 py-1 text-xs font-mono border border-[var(--color-border)] rounded bg-[var(--color-surface)]"
          />
          <button
            onClick={() => {
              if (pattern.trim()) {
                onAddRule(field, pattern.trim());
                setPattern("");
              }
            }}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]"
          >
            <Plus size={11} /> Add rule
          </button>
        </div>
      </CardBody>
    </Card>
  );
}
