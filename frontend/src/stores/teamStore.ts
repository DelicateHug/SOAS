/**
 * Team state management with Zustand.
 * Tracks the user's active team selection for filtering resources.
 * A team must ALWAYS be selected — there is no "all teams" view.
 */

import { create } from "zustand";

interface TeamState {
  activeTeamId: string | null;
  setActiveTeam: (id: string) => void;
}

export const useTeamStore = create<TeamState>((set) => ({
  activeTeamId: localStorage.getItem("active_team_id") || null,

  setActiveTeam: (id) => {
    localStorage.setItem("active_team_id", id);
    set({ activeTeamId: id });
  },
}));
