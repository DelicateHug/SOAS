import { useState, useRef, useEffect } from "react";
import { useParams, Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import {
  formatDate,
  caseStatusColors,
} from "@/lib/utils";
import { ArrowLeft, ChevronDown, X } from "lucide-react";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { EntityIssuesPanel } from "@/components/issues/EntityIssuesPanel";
import { OverviewTab } from "./tabs/OverviewTab";
import { TimelineTab } from "./tabs/TimelineTab";
import { ChatTab } from "./tabs/ChatTab";
import { NotesTab } from "./tabs/NotesTab";
import { FilesTab } from "./tabs/FilesTab";
import { FormsTab } from "./tabs/FormsTab";
import { AutomationsTab } from "./tabs/AutomationsTab";
import type {
  CaseItem,
  CaseStatus,
  UserRead,
} from "@/types/api";

const priorityLabels: Record<number, string> = {
  1: "P1 - Critical",
  2: "P2 - High",
  3: "P3 - Medium",
  4: "P4 - Low",
  5: "P5 - Minimal",
};

const priorityColors: Record<number, string> = {
  1: "bg-red-500 text-white",
  2: "bg-orange-500 text-white",
  3: "bg-yellow-500 text-black",
  4: "bg-blue-500 text-white",
  5: "bg-gray-500 text-white",
};

const nextStatuses: Record<string, CaseStatus[]> = {
  open: ["investigating", "pending", "closed"],
  investigating: ["pending", "closed"],
  pending: ["investigating", "closed"],
  closed: ["archived"],
};

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "timeline", label: "Timeline" },
  { id: "chat", label: "Chat" },
  { id: "notes", label: "Notes" },
  { id: "files", label: "Files" },
  { id: "forms", label: "Forms" },
  { id: "automations", label: "Automations" },
  { id: "issues", label: "Issues" },
] as const;

type TabId = (typeof tabs)[number]["id"];

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const activeTab = (searchParams.get("tab") as TabId) || "overview";
  const setActiveTab = (tab: TabId) => {
    setSearchParams({ tab });
  };

  // Editing states
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState("");
  const [showPriorityDropdown, setShowPriorityDropdown] = useState(false);
  const [showLeadDropdown, setShowLeadDropdown] = useState(false);

  // Status transition dialog
  const [pendingStatus, setPendingStatus] = useState<CaseStatus | null>(null);
  const [cascadeChecked, setCascadeChecked] = useState(false);

  const { data: caseData, isLoading } = useQuery({
    queryKey: ["case", id],
    queryFn: () => api.get<CaseItem>(`/cases/${id}`),
    enabled: !!id,
  });

  const { data: users } = useQuery({
    queryKey: ["users-list"],
    queryFn: () =>
      api.get<{ data: UserRead[] }>("/users?per_page=100"),
  });

  const updateCase = useToastMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.patch<CaseItem>(`/cases/${id}`, body),
    loadingMessage: "Updating case...",
    successMessage: "Case updated.",
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["case", id] });
      queryClient.invalidateQueries({ queryKey: ["case-timeline", id] });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 border-2 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="text-center py-16">
        <p className="text-[hsl(var(--muted-foreground))]">Group not found</p>
        <button
          onClick={() => navigate("/cases")}
          className="mt-3 text-sm text-[hsl(var(--primary))] hover:underline"
        >
          Back to Incident Groups
        </button>
      </div>
    );
  }

  const available = nextStatuses[caseData.status] || [];

  const handleStatusTransition = () => {
    if (!pendingStatus) return;
    updateCase.mutate(
      {
        status: pendingStatus,
        cascade_status: cascadeChecked,
      },
      {
        onSuccess: () => {
          setPendingStatus(null);
          setCascadeChecked(false);
        },
      }
    );
  };

  const saveTitle = () => {
    if (titleDraft.trim() && titleDraft !== caseData.title) {
      updateCase.mutate({ title: titleDraft.trim() });
    }
    setEditingTitle(false);
  };

  const saveDesc = () => {
    if (descDraft !== (caseData.description || "")) {
      updateCase.mutate({ description: descDraft });
    }
    setEditingDesc(false);
  };

  return (
    <div className="max-w-5xl">
      {/* Breadcrumb + status transition */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(-1)}
            className="p-1 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
            aria-label="Go back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <Link
            to="/cases"
            className="text-xs text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
          >
            Incident Groups /
          </Link>
        </div>

        {available.length > 0 && (
          <div className="flex gap-2">
            {available.map((status) => (
              <button
                key={status}
                onClick={() => setPendingStatus(status)}
                disabled={updateCase.isPending}
                className="px-3 py-1.5 border border-[hsl(var(--border))] rounded-md text-xs font-medium hover:bg-[hsl(var(--accent))] transition-colors disabled:opacity-50"
              >
                Move to {status}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Title + badges */}
      <div className="mb-6">
        <div className="flex items-center gap-2 flex-wrap mb-2">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${caseStatusColors[caseData.status] || "bg-gray-500/15 text-gray-400"}`}
          >
            {caseData.status}
          </span>
          <PriorityDropdown
            priority={caseData.priority}
            open={showPriorityDropdown}
            onToggle={() => setShowPriorityDropdown(!showPriorityDropdown)}
            onSelect={(p) => {
              updateCase.mutate({ priority: p });
              setShowPriorityDropdown(false);
            }}
          />
        </div>

        {/* Editable title */}
        {editingTitle ? (
          <input
            autoFocus
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveTitle();
              if (e.key === "Escape") setEditingTitle(false);
            }}
            className="text-xl font-semibold leading-tight mb-2 w-full bg-transparent border-b border-[hsl(var(--primary))] outline-none"
          />
        ) : (
          <h1
            className="text-xl font-semibold leading-tight mb-2 cursor-pointer hover:text-[hsl(var(--primary))] transition-colors"
            onClick={() => {
              setTitleDraft(caseData.title);
              setEditingTitle(true);
            }}
            title="Click to edit"
          >
            {caseData.title}
          </h1>
        )}

        {/* Editable description */}
        {editingDesc ? (
          <textarea
            autoFocus
            value={descDraft}
            onChange={(e) => setDescDraft(e.target.value)}
            onBlur={saveDesc}
            onKeyDown={(e) => {
              if (e.key === "Escape") setEditingDesc(false);
            }}
            rows={3}
            className="w-full text-sm text-[hsl(var(--muted-foreground))] bg-transparent border border-[hsl(var(--border))] rounded p-2 outline-none resize-none"
          />
        ) : (
          <p
            className="text-sm text-[hsl(var(--muted-foreground))] cursor-pointer hover:text-[hsl(var(--foreground))] transition-colors"
            onClick={() => {
              setDescDraft(caseData.description || "");
              setEditingDesc(true);
            }}
            title="Click to edit"
          >
            {caseData.description || "Add a description..."}
          </p>
        )}

        {/* Meta row */}
        <div className="flex items-center gap-4 mt-3 text-xs text-[hsl(var(--muted-foreground))] flex-wrap">
          <div className="flex items-center gap-1.5">
            <UserAvatar
              displayName={caseData.created_by.display_name}
              size="sm"
            />
            <span>{caseData.created_by.display_name}</span>
          </div>
          <span>{formatDate(caseData.created_at)}</span>
          <span>{caseData.incident_count} linked incidents</span>

          {/* Lead assignment */}
          <div className="relative">
            <button
              onClick={() => setShowLeadDropdown(!showLeadDropdown)}
              className="flex items-center gap-1.5 hover:text-[hsl(var(--foreground))] transition-colors"
            >
              <span>Lead:</span>
              {caseData.lead ? (
                <>
                  <UserAvatar
                    displayName={caseData.lead.display_name}
                    size="sm"
                  />
                  <span>{caseData.lead.display_name}</span>
                </>
              ) : (
                <span className="italic">Unassigned</span>
              )}
              <ChevronDown className="w-3 h-3" />
            </button>
            {showLeadDropdown && (
              <LeadDropdown
                users={users?.data || []}
                currentLeadId={caseData.lead?.id}
                onSelect={(userId) => {
                  updateCase.mutate({ lead_id: userId });
                  setShowLeadDropdown(false);
                }}
                onClear={() => {
                  updateCase.mutate({ lead_id: null });
                  setShowLeadDropdown(false);
                }}
                onClose={() => setShowLeadDropdown(false)}
              />
            )}
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="border-b border-[hsl(var(--border))] mb-6">
        <div className="flex gap-0 -mb-px">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-[hsl(var(--primary))] text-[hsl(var(--foreground))]"
                  : "border-transparent text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] hover:border-[hsl(var(--border))]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <OverviewTab caseData={caseData} caseId={id!} />
      )}
      {activeTab === "timeline" && <TimelineTab caseId={id!} />}
      {activeTab === "chat" && <ChatTab caseId={id!} />}
      {activeTab === "notes" && <NotesTab caseId={id!} />}
      {activeTab === "files" && <FilesTab caseId={id!} />}
      {activeTab === "forms" && <FormsTab caseId={id!} />}
      {activeTab === "automations" && <AutomationsTab caseId={id!} />}
      {activeTab === "issues" && (
        <div className="border border-[hsl(var(--border))] rounded-lg p-4">
          <EntityIssuesPanel
            targetType="case"
            targetId={id!}
            targetName={caseData.title}
          />
        </div>
      )}

      {/* Status transition confirmation dialog */}
      {pendingStatus && (
        <StatusTransitionDialog
          targetStatus={pendingStatus}
          hasIncidents={caseData.incidents.length > 0}
          cascadeChecked={cascadeChecked}
          onCascadeChange={setCascadeChecked}
          onConfirm={handleStatusTransition}
          onCancel={() => {
            setPendingStatus(null);
            setCascadeChecked(false);
          }}
          isPending={updateCase.isPending}
        />
      )}
    </div>
  );
}

/* ---- Sub-components ---- */

function PriorityDropdown({
  priority,
  open,
  onToggle,
  onSelect,
}: {
  priority: number;
  open: boolean;
  onToggle: () => void;
  onSelect: (p: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onToggle();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onToggle]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={onToggle}
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${priorityColors[priority]} cursor-pointer`}
      >
        {priorityLabels[priority]}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 w-40 border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg py-1">
          {[1, 2, 3, 4, 5].map((p) => (
            <button
              key={p}
              onClick={() => onSelect(p)}
              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-[hsl(var(--accent))] ${p === priority ? "font-bold" : ""}`}
            >
              {priorityLabels[p]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function LeadDropdown({
  users,
  currentLeadId,
  onSelect,
  onClear,
  onClose,
}: {
  users: UserRead[];
  currentLeadId?: string;
  onSelect: (userId: string) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute left-0 top-full mt-1 z-50 w-56 border border-[hsl(var(--border))] rounded-md bg-[hsl(var(--popover))] shadow-lg"
    >
      <div className="max-h-48 overflow-y-auto py-1">
        {currentLeadId && (
          <button
            onClick={onClear}
            className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-[hsl(var(--accent))]"
          >
            Unassign lead
          </button>
        )}
        {users.map((user) => (
          <button
            key={user.id}
            onClick={() => onSelect(user.id)}
            className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[hsl(var(--accent))] ${user.id === currentLeadId ? "font-bold" : ""}`}
          >
            <UserAvatar displayName={user.display_name} size="sm" />
            {user.display_name}
          </button>
        ))}
      </div>
    </div>
  );
}

function StatusTransitionDialog({
  targetStatus,
  hasIncidents,
  cascadeChecked,
  onCascadeChange,
  onConfirm,
  onCancel,
  isPending,
}: {
  targetStatus: CaseStatus;
  hasIncidents: boolean;
  cascadeChecked: boolean;
  onCascadeChange: (v: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg shadow-lg w-96 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Confirm Status Change</h3>
          <button
            onClick={onCancel}
            className="p-1 rounded hover:bg-[hsl(var(--accent))] text-[hsl(var(--muted-foreground))]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mb-4">
          Change case status to{" "}
          <span className="font-medium text-[hsl(var(--foreground))]">
            {targetStatus}
          </span>
          ?
        </p>
        {hasIncidents && (
          <label className="flex items-center gap-2 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={cascadeChecked}
              onChange={(e) => onCascadeChange(e.target.checked)}
              className="rounded border-[hsl(var(--input))]"
            />
            <span className="text-sm">Also update linked incidents</span>
          </label>
        )}
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm border border-[hsl(var(--border))] rounded-md hover:bg-[hsl(var(--accent))] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className="px-3 py-1.5 text-sm bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {isPending ? "Updating..." : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
