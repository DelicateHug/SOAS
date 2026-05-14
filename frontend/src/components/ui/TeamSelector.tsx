/**
 * Team selector dropdown for the sidebar.
 * Users must always be viewing a specific team — there is no "all teams" view.
 * The default team serves as the global team that all users start with.
 */

import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useTeamStore } from "@/stores/teamStore";
import { Users, ChevronDown } from "lucide-react";

export function TeamSelector({ collapsed }: { collapsed: boolean }) {
  const user = useAuthStore((s) => s.user);
  const { activeTeamId, setActiveTeam } = useTeamStore();

  const teams = user?.teams || [];

  // Auto-select first team if none is active (or if active team is no longer valid)
  useEffect(() => {
    if (teams.length === 0) return;
    const isValid = teams.some((t) => t.id === activeTeamId);
    if (!activeTeamId || !isValid) {
      // Prefer the default team, fallback to first
      const defaultTeam = teams.find((t) => t.name === "default") || teams[0];
      if (defaultTeam) setActiveTeam(defaultTeam.id);
    }
  }, [teams, activeTeamId, setActiveTeam]);

  if (teams.length === 0) return null;

  const activeTeam = teams.find((t) => t.id === activeTeamId);

  if (collapsed) {
    return (
      <div
        className="flex justify-center px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-primary)]/5"
        title={activeTeam ? `Team: ${activeTeam.name}` : "Select team"}
      >
        <div className="w-7 h-7 rounded flex items-center justify-center bg-[var(--color-primary)]/15 text-[var(--color-primary)]">
          <Users className="w-3.5 h-3.5" />
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-primary)]/5">
      <label className="block text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-1">
        Team
      </label>
      <div className="relative">
        <select
          value={activeTeamId || ""}
          onChange={(e) => setActiveTeam(e.target.value)}
          className="w-full appearance-none text-xs font-medium rounded px-2.5 py-1.5 pr-7 border focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] cursor-pointer bg-[var(--color-primary)]/10 text-[var(--color-primary)] border-[var(--color-primary)]/30"
        >
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 pointer-events-none text-[var(--color-primary)]" />
      </div>
    </div>
  );
}
