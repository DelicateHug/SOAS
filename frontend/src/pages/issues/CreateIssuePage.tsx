import { useState, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ArrowLeft, Loader2, Search } from "lucide-react";
import type { UserRead, IssueLinkTargetType } from "@/types/api";

const TARGET_TYPE_LABELS: Record<IssueLinkTargetType, string> = {
  incident: "Incident",
  automation: "Automation",
  scheduled_job: "Scheduled Job",
  role: "Role",
  code_library_block: "Code Block",
  normalization_rule: "Normalization Rule",
  case: "Incident Group",
  execution_log: "Execution",
};

interface EntityOption {
  id: string;
  label: string;
  sub?: string;
}

const ENTITY_ENDPOINTS: Record<string, string> = {
  incident: "/incidents?per_page=100",
  automation: "/automations?per_page=100",
  scheduled_job: "/jobs?per_page=100",
  role: "/roles",
  code_library_block: "/code-library?per_page=100",
  normalization_rule: "/normalization/rules",
  case: "/cases?per_page=100",
  execution_log: "/executions?per_page=100",
};

function extractEntityOptions(type: string, data: unknown): EntityOption[] {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const items: any[] = Array.isArray(data) ? data : (data as any)?.data ?? [];
  return items.map((item) => {
    switch (type) {
      case "incident":
        return { id: item.id, label: item.title, sub: item.status };
      case "automation":
        return { id: item.id, label: item.name, sub: item.description };
      case "scheduled_job":
        return { id: item.id, label: item.name, sub: item.automation_name };
      case "role":
        return { id: item.id, label: item.display_name, sub: item.name };
      case "code_library_block":
        return { id: item.id, label: item.name, sub: item.language };
      case "normalization_rule":
        return { id: item.id, label: item.target_field, sub: item.rule_type };
      case "case":
        return { id: item.id, label: item.title, sub: item.status };
      case "execution_log":
        return { id: item.id, label: item.automation_name ?? item.id.slice(0, 8), sub: item.status };
      default:
        return { id: item.id, label: item.name ?? item.title ?? item.id };
    }
  });
}

export function CreateIssuePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Pre-populate link from query params (when creating from entity pages)
  const initialLinkType = searchParams.get("linkType") as IssueLinkTargetType | null;
  const initialLinkId = searchParams.get("linkId");
  const initialLinkName = searchParams.get("linkName");

  const [form, setForm] = useState({
    title: "",
    description: "",
    assigned_to: "" as string,
  });

  const [linkType, setLinkType] = useState<string>(initialLinkType ?? "");
  const [linkId, setLinkId] = useState(initialLinkId ?? "");
  const [linkName] = useState(initialLinkName ?? "");
  const [entityFilter, setEntityFilter] = useState("");
  const [entityDropdownOpen, setEntityDropdownOpen] = useState(false);
  const [selectedEntityName, setSelectedEntityName] = useState("");

  // Fetch users for assignment dropdown
  const { data: users } = useQuery({
    queryKey: ["users-brief"],
    queryFn: () => api.get<{ data: UserRead[] }>("/users?per_page=100"),
  });

  // Fetch entities for the selected link type
  const { data: rawEntities, isLoading: entitiesLoading } = useQuery({
    queryKey: ["entity-options", linkType],
    queryFn: () => api.get<unknown>(ENTITY_ENDPOINTS[linkType]!),
    enabled: !!linkType && !!ENTITY_ENDPOINTS[linkType],
    staleTime: 30_000,
  });

  const entityOptions = useMemo(() => {
    if (!rawEntities || !linkType) return [];
    return extractEntityOptions(linkType, rawEntities);
  }, [rawEntities, linkType]);

  const filteredEntities = useMemo(() => {
    if (!entityFilter) return entityOptions;
    const lower = entityFilter.toLowerCase();
    return entityOptions.filter(
      (e) =>
        e.label.toLowerCase().includes(lower) ||
        e.sub?.toLowerCase().includes(lower)
    );
  }, [entityOptions, entityFilter]);

  const create = useMutation({
    mutationFn: () => {
      const links = linkType && linkId
        ? [{ target_type: linkType, target_id: linkId }]
        : [];
      return api.post<{ id: string }>("/issues", {
        title: form.title,
        description: form.description || null,
        assigned_to: form.assigned_to || null,
        links,
      });
    },
    onSuccess: (data: { id: string }) => {
      navigate(`/issues/${data.id}`);
    },
  });

  return (
    <div className="max-w-2xl">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] mb-4"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      <h1 className="text-2xl font-bold mb-6">Create Issue</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
        className="flex flex-col gap-4"
      >
        {/* Title */}
        <div>
          <label className="block text-sm font-medium mb-1">Title</label>
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="Issue title..."
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
            required
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Describe the issue..."
            rows={4}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] resize-y"
          />
        </div>

        {/* Assigned To */}
        <div>
          <label className="block text-sm font-medium mb-1">Assign To</label>
          <select
            value={form.assigned_to}
            onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
            className="w-full px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))]"
          >
            <option value="">Unassigned</option>
            {users?.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.display_name} ({u.username})
              </option>
            ))}
          </select>
        </div>

        {/* Link to entity */}
        <div className="border border-[hsl(var(--border))] rounded-lg p-4">
          <label className="block text-sm font-medium mb-2">Link to Entity (optional)</label>
          {initialLinkType && initialLinkId ? (
            <div className="text-sm text-[hsl(var(--muted-foreground))]">
              Linked to: <strong>{TARGET_TYPE_LABELS[initialLinkType] ?? initialLinkType}</strong>
              {linkName && ` — ${linkName}`}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <select
                value={linkType}
                onChange={(e) => {
                  setLinkType(e.target.value);
                  setLinkId("");
                  setSelectedEntityName("");
                  setEntityFilter("");
                }}
                className="px-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
              >
                <option value="">Select type...</option>
                {Object.entries(TARGET_TYPE_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
              {linkType && (
                <div className="relative">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
                    <input
                      type="text"
                      value={entityDropdownOpen ? entityFilter : selectedEntityName}
                      onChange={(e) => {
                        setEntityFilter(e.target.value);
                        if (!entityDropdownOpen) setEntityDropdownOpen(true);
                      }}
                      onFocus={() => {
                        setEntityFilter(selectedEntityName);
                        setEntityDropdownOpen(true);
                      }}
                      onBlur={() => {
                        setTimeout(() => setEntityDropdownOpen(false), 150);
                      }}
                      placeholder={`Search ${TARGET_TYPE_LABELS[linkType as IssueLinkTargetType] ?? linkType}...`}
                      className="w-full pl-8 pr-3 py-2 border border-[hsl(var(--input))] rounded-md bg-[hsl(var(--background))] text-sm"
                    />
                    {entitiesLoading && (
                      <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-[hsl(var(--muted-foreground))]" />
                    )}
                  </div>
                  {entityDropdownOpen && !entitiesLoading && (
                    <div className="absolute z-50 top-full left-0 right-0 mt-0.5 max-h-52 overflow-y-auto border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg">
                      {filteredEntities.length === 0 ? (
                        <div className="px-3 py-2 text-sm text-[hsl(var(--muted-foreground))]">
                          No results found
                        </div>
                      ) : (
                        filteredEntities.map((entity) => (
                          <button
                            key={entity.id}
                            type="button"
                            className={`w-full text-left px-3 py-2 text-sm hover:bg-[hsl(var(--accent))] flex flex-col ${
                              entity.id === linkId ? "bg-[hsl(var(--accent))]" : ""
                            }`}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              setLinkId(entity.id);
                              setSelectedEntityName(entity.label);
                              setEntityFilter(entity.label);
                              setEntityDropdownOpen(false);
                            }}
                          >
                            <span className="font-medium">{entity.label}</span>
                            {entity.sub && (
                              <span className="text-xs text-[hsl(var(--muted-foreground))] truncate">
                                {entity.sub}
                              </span>
                            )}
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={create.isPending || !form.title.trim()}
            className="px-4 py-2 bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 disabled:opacity-50 text-sm"
          >
            {create.isPending ? "Creating..." : "Create Issue"}
          </button>
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="px-4 py-2 border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))] text-sm"
          >
            Cancel
          </button>
        </div>

        {create.isError && (
          <p className="text-sm text-red-400">
            Failed to create issue. Please try again.
          </p>
        )}
      </form>
    </div>
  );
}
