/**
 * Team Variables page — shows the active team's variables.
 * Redirects to the team detail page with the Variables tab selected.
 */

import { Navigate } from "react-router-dom";
import { useTeamStore } from "@/stores/teamStore";

export function TeamVariablesPage() {
  const activeTeamId = useTeamStore((s) => s.activeTeamId);

  if (!activeTeamId) {
    return (
      <div className="p-8 text-center text-[hsl(var(--muted-foreground))]">
        No team selected. Please select a team first.
      </div>
    );
  }

  return <Navigate to={`/teams/${activeTeamId}?tab=variables`} replace />;
}
