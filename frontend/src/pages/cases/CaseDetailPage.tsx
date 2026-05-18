import { useState, useRef, useEffect } from "react";
import { useParams, Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";
import {
  formatDate,
  caseStatusColors,
} from "@/lib/utils";
import { ChevronLeft, ChevronDown, X, Clock } from "lucide-react";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { EntityIssuesPanel } from "@/components/issues/EntityIssuesPanel";
import { AIActionsBar } from "@/components/ai/AIActionsBar";
import { StartWorkButton } from "@/components/work/StartWorkButton";
import { WorkGateProvider, useWorkGate } from "@/components/work/WorkGateContext";
import { WorkGateBanner } from "@/components/work/WorkGateBanner";
import { WriteGuard } from "@/components/work/WriteGuard";
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
        <div className="h-6 w-6 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="text-center py-16">
        <p className="text-[var(--color-text-muted)]">Group not found</p>
        <button
          onClick={() => navigate("/cases")}
          className="mt-3 text-sm text-[var(--color-primary)] hover:underline"
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
    <WorkGateProvider caseId={id!}>
      <CaseLayout
        id={id!}
        caseData={caseData}
        users={users?.data || []}
        available={available}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        editingTitle={editingTitle}
        setEditingTitle={setEditingTitle}
        titleDraft={titleDraft}
        setTitleDraft={setTitleDraft}
        editingDesc={editingDesc}
        setEditingDesc={setEditingDesc}
        descDraft={descDraft}
        setDescDraft={setDescDraft}
        showPriorityDropdown={showPriorityDropdown}
        setShowPriorityDropdown={setShowPriorityDropdown}
        showLeadDropdown={showLeadDropdown}
        setShowLeadDropdown={setShowLeadDropdown}
        pendingStatus={pendingStatus}
        setPendingStatus={setPendingStatus}
        cascadeChecked={cascadeChecked}
        setCascadeChecked={setCascadeChecked}
        updateCase={updateCase}
        navigate={navigate}
        saveTitle={saveTitle}
        saveDesc={saveDesc}
        handleStatusTransition={handleStatusTransition}
      />
    </WorkGateProvider>
  );
}

// Inner layout so it can call useWorkGate (must be inside WorkGateProvider).
// Long arg list is the trade-off for not lifting all state up; the gating
// pattern keeps everything else intentionally untouched.
type CaseLayoutProps = {
  id: string;
  caseData: CaseItem;
  users: UserRead[];
  available: CaseStatus[];
  activeTab: TabId;
  setActiveTab: (t: TabId) => void;
  editingTitle: boolean;
  setEditingTitle: (v: boolean) => void;
  titleDraft: string;
  setTitleDraft: (v: string) => void;
  editingDesc: boolean;
  setEditingDesc: (v: boolean) => void;
  descDraft: string;
  setDescDraft: (v: string) => void;
  showPriorityDropdown: boolean;
  setShowPriorityDropdown: (v: boolean) => void;
  showLeadDropdown: boolean;
  setShowLeadDropdown: (v: boolean) => void;
  pendingStatus: CaseStatus | null;
  setPendingStatus: (v: CaseStatus | null) => void;
  cascadeChecked: boolean;
  setCascadeChecked: (v: boolean) => void;
  updateCase: { mutate: (body: Record<string, unknown>, opts?: { onSuccess?: () => void }) => void; isPending: boolean };
  navigate: ReturnType<typeof useNavigate>;
  saveTitle: () => void;
  saveDesc: () => void;
  handleStatusTransition: () => void;
};

function CaseLayout(p: CaseLayoutProps) {
  const { isWorking } = useWorkGate();
  const { caseData, users, id, available } = p;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
      {/* ============ Sidebar ============ */}
      <aside className="space-y-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
          <button
            onClick={() => p.navigate(-1)}
            className="p-1 -ml-1 rounded hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text)] transition-colors"
            aria-label="Go back"
          >
            <ChevronLeft size={14} />
          </button>
          <Link to="/cases" className="hover:text-[var(--color-text)] transition-colors">
            Incident Groups
          </Link>
        </div>

        {/* Status */}
        <div className="space-y-2">
          <SidebarLabel>Status</SidebarLabel>
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded text-xs font-medium ${caseStatusColors[caseData.status] || "bg-gray-500/15 text-gray-400"}`}
          >
            {caseData.status}
          </span>
        </div>

        {/* Priority */}
        <div className="space-y-2">
          <SidebarLabel>Priority</SidebarLabel>
          <WriteGuard blockedTitle="Start work to change priority">
            <PriorityDropdown
              priority={caseData.priority}
              open={p.showPriorityDropdown}
              onToggle={() => p.setShowPriorityDropdown(!p.showPriorityDropdown)}
              onSelect={(pr) => {
                p.updateCase.mutate({ priority: pr });
                p.setShowPriorityDropdown(false);
              }}
            />
          </WriteGuard>
        </div>

        {/* Start work */}
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-2">
          <SidebarLabel>
            <Clock size={11} className="inline mr-1 -mt-0.5" /> Work session
          </SidebarLabel>
          <StartWorkButton caseId={caseData.id} />
          {!isWorking && (
            <p className="text-[10px] text-[var(--color-text-muted)] leading-relaxed">
              Editing is locked until you start a work session on this group.
            </p>
          )}
        </div>

        {/* Transitions */}
        {available.length > 0 && (
          <div className="space-y-2">
            <SidebarLabel>Transition to</SidebarLabel>
            <div className="flex flex-col gap-1.5">
              {available.map((status) => (
                <button
                  key={status}
                  onClick={() => p.setPendingStatus(status)}
                  disabled={!isWorking || p.updateCase.isPending}
                  className="px-2.5 py-1.5 border border-[var(--color-border)] rounded text-xs text-left hover:bg-[var(--color-surface-2)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  title={!isWorking ? "Start work to transition" : `Move to ${status}`}
                >
                  Move to {status}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Lead */}
        <div className="space-y-2">
          <SidebarLabel>Lead</SidebarLabel>
          <WriteGuard blockedTitle="Start work to change lead">
            <div className="relative">
              <button
                onClick={() => p.setShowLeadDropdown(!p.showLeadDropdown)}
                className="w-full flex items-center justify-between gap-1.5 px-2.5 py-1.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-surface-2)] text-xs"
              >
                {caseData.lead ? (
                  <span className="inline-flex items-center gap-1.5">
                    <UserAvatar displayName={caseData.lead.display_name} size="sm" />
                    {caseData.lead.display_name}
                  </span>
                ) : (
                  <span className="italic text-[var(--color-text-muted)]">Unassigned</span>
                )}
                <ChevronDown className="w-3 h-3 shrink-0" />
              </button>
              {p.showLeadDropdown && (
                <LeadDropdown
                  users={users}
                  currentLeadId={caseData.lead?.id}
                  onSelect={(userId) => {
                    p.updateCase.mutate({ lead_id: userId });
                    p.setShowLeadDropdown(false);
                  }}
                  onClear={() => {
                    p.updateCase.mutate({ lead_id: null });
                    p.setShowLeadDropdown(false);
                  }}
                  onClose={() => p.setShowLeadDropdown(false)}
                />
              )}
            </div>
          </WriteGuard>
        </div>

        {/* Created by */}
        <div className="space-y-2">
          <SidebarLabel>Created by</SidebarLabel>
          <div className="flex items-center gap-1.5 text-xs text-[var(--color-text)]">
            <UserAvatar displayName={caseData.created_by.display_name} size="sm" />
            <div>
              <div>{caseData.created_by.display_name}</div>
              <div className="text-[10px] text-[var(--color-text-muted)]">{formatDate(caseData.created_at)}</div>
            </div>
          </div>
        </div>

        {/* Linked incidents */}
        <div className="space-y-2">
          <SidebarLabel>Linked incidents</SidebarLabel>
          <div className="text-xs text-[var(--color-text-muted)]">{caseData.incident_count}</div>
        </div>

        {/* AI actions */}
        <div className="pt-2 border-t border-[var(--color-border)]">
          <SidebarLabel>AI</SidebarLabel>
          <div className="mt-2">
            <AIActionsBar
              pageKey="case_detail"
              context={{
                case_id: caseData.id,
                title: caseData.title,
                status: caseData.status,
                priority: caseData.priority,
              }}
            />
          </div>
        </div>
      </aside>

      {/* ============ Main workspace ============ */}
      <main className="min-w-0">
        {/* Editable title */}
        <div className="mb-4">
          {p.editingTitle ? (
            <input
              autoFocus
              value={p.titleDraft}
              onChange={(e) => p.setTitleDraft(e.target.value)}
              onBlur={p.saveTitle}
              onKeyDown={(e) => {
                if (e.key === "Enter") p.saveTitle();
                if (e.key === "Escape") p.setEditingTitle(false);
              }}
              className="text-2xl font-semibold leading-tight w-full bg-transparent border-b border-[var(--color-primary)] outline-none text-[var(--color-text)]"
            />
          ) : (
            <h1
              className={`text-2xl font-semibold leading-tight text-[var(--color-text)] ${isWorking ? "cursor-pointer hover:text-[var(--color-primary)] transition-colors" : ""}`}
              onClick={() => {
                if (!isWorking) return;
                p.setTitleDraft(caseData.title);
                p.setEditingTitle(true);
              }}
              title={isWorking ? "Click to edit" : "Start work to edit"}
            >
              {caseData.title}
            </h1>
          )}

          {/* Editable description */}
          {p.editingDesc ? (
            <textarea
              autoFocus
              value={p.descDraft}
              onChange={(e) => p.setDescDraft(e.target.value)}
              onBlur={p.saveDesc}
              onKeyDown={(e) => {
                if (e.key === "Escape") p.setEditingDesc(false);
              }}
              rows={3}
              className="mt-2 w-full text-sm text-[var(--color-text-muted)] bg-transparent border border-[var(--color-border)] rounded p-2 outline-none resize-none"
            />
          ) : (
            <p
              className={`mt-1.5 text-sm text-[var(--color-text-muted)] ${isWorking ? "cursor-pointer hover:text-[var(--color-text)] transition-colors" : ""}`}
              onClick={() => {
                if (!isWorking) return;
                p.setDescDraft(caseData.description || "");
                p.setEditingDesc(true);
              }}
              title={isWorking ? "Click to edit" : "Start work to edit"}
            >
              {caseData.description || (isWorking ? "Add a description..." : "No description")}
            </p>
          )}
        </div>

        {/* Gate banner */}
        <WorkGateBanner />

        {/* Tab bar */}
        <div className="border-b border-[var(--color-border)] mb-6">
          <div className="flex gap-0 -mb-px overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => p.setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  p.activeTab === tab.id
                    ? "border-[var(--color-primary)] text-[var(--color-text)]"
                    : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-border)]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        {p.activeTab === "overview" && <OverviewTab caseData={caseData} caseId={id} />}
        {p.activeTab === "timeline" && <TimelineTab caseId={id} />}
        {p.activeTab === "chat" && <ChatTab caseId={id} />}
        {p.activeTab === "notes" && <NotesTab caseId={id} />}
        {p.activeTab === "files" && <FilesTab caseId={id} />}
        {p.activeTab === "forms" && <FormsTab caseId={id} />}
        {p.activeTab === "automations" && <AutomationsTab caseId={id} />}
        {p.activeTab === "issues" && (
          <div className="border border-[var(--color-border)] rounded-lg p-4">
            <EntityIssuesPanel targetType="case" targetId={id} targetName={caseData.title} />
          </div>
        )}

        {/* Status transition dialog */}
        {p.pendingStatus && (
          <StatusTransitionDialog
            targetStatus={p.pendingStatus}
            hasIncidents={caseData.incidents.length > 0}
            cascadeChecked={p.cascadeChecked}
            onCascadeChange={p.setCascadeChecked}
            onConfirm={p.handleStatusTransition}
            onCancel={() => {
              p.setPendingStatus(null);
              p.setCascadeChecked(false);
            }}
            isPending={p.updateCase.isPending}
          />
        )}
      </main>
    </div>
  );
}

function SidebarLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
      {children}
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
        <div className="absolute left-0 top-full mt-1 z-50 w-40 border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] shadow-lg py-1">
          {[1, 2, 3, 4, 5].map((p) => (
            <button
              key={p}
              onClick={() => onSelect(p)}
              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-[var(--color-surface-2)] ${p === priority ? "font-bold" : ""}`}
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
      className="absolute left-0 top-full mt-1 z-50 w-56 border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] shadow-lg"
    >
      <div className="max-h-48 overflow-y-auto py-1">
        {currentLeadId && (
          <button
            onClick={onClear}
            className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-[var(--color-surface-2)]"
          >
            Unassign lead
          </button>
        )}
        {users.map((user) => (
          <button
            key={user.id}
            onClick={() => onSelect(user.id)}
            className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-[var(--color-surface-2)] ${user.id === currentLeadId ? "font-bold" : ""}`}
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
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg w-96 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Confirm Status Change</h3>
          <button
            onClick={onCancel}
            className="p-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-sm text-[var(--color-text-muted)] mb-4">
          Change case status to{" "}
          <span className="font-medium text-[var(--color-text)]">
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
              className="rounded border-[var(--color-border)]"
            />
            <span className="text-sm">Also update linked incidents</span>
          </label>
        )}
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded-md hover:bg-[var(--color-surface-2)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            className="px-3 py-1.5 text-sm bg-[var(--color-primary)] text-[#ffffff] rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {isPending ? "Updating..." : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}
