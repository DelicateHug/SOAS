import { useSearchParams } from "react-router-dom";
import { Terminal, Clock } from "lucide-react";
import { ExecutionsTab } from "./ExecutionsTab";
import { JobsTab } from "./JobsTab";

type Tab = "executions" | "jobs";

const tabs: { id: Tab; label: string; icon: typeof Terminal }[] = [
  { id: "executions", label: "Executions", icon: Terminal },
  { id: "jobs", label: "Scheduled Jobs", icon: Clock },
];

export function ExecutionListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = (searchParams.get("tab") as Tab) || "executions";

  const setTab = (tab: Tab) => {
    setSearchParams({ tab });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Execution Logs</h1>

      {/* Tab navigation */}
      <div className="flex gap-1 mb-6 border-b border-[var(--color-border)]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[var(--color-primary)] text-[var(--color-text)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "executions" && <ExecutionsTab />}
      {activeTab === "jobs" && <JobsTab />}
    </div>
  );
}
