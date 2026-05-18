/**
 * Work-gate context: tells every descendant whether the current user has an
 * active work session on the current incident/case. When false, mutating UI
 * (forms, automations, status transitions, notes/files writes) must disable
 * itself. Read views remain unaffected.
 *
 * Usage at the page level:
 *   <WorkGateProvider incidentId={id}>
 *     <IncidentDetailLayout ... />
 *   </WorkGateProvider>
 *
 * From any descendant:
 *   const { isWorking } = useWorkGate();
 *   <button disabled={!isWorking}>…</button>
 */
import { createContext, useContext, type ReactNode } from "react";
import { useWorkSession } from "@/hooks/useWorkSession";

interface WorkGateValue {
  /** True when the current user has an `active` (not paused) session on this exact target. */
  isWorking: boolean;
  /** True when there's an active session, but on a different target. UI may want to surface
   *  that a switch will auto-pause the other. */
  workingOnOther: boolean;
  /** True while the work-session query is in flight (initial page load). */
  isLoading: boolean;
}

const WorkGateContext = createContext<WorkGateValue>({
  isWorking: false,
  workingOnOther: false,
  isLoading: false,
});

interface ProviderProps {
  incidentId?: string;
  caseId?: string;
  children: ReactNode;
}

export function WorkGateProvider({ incidentId, caseId, children }: ProviderProps) {
  const { current, isLoading } = useWorkSession();

  const targetMatches =
    current &&
    ((incidentId && current.incident_id === incidentId) ||
      (caseId && current.case_id === caseId));

  const isWorking = !!targetMatches && current?.status === "active";
  const workingOnOther = !!current && current.status === "active" && !targetMatches;

  return (
    <WorkGateContext.Provider value={{ isWorking, workingOnOther, isLoading }}>
      {children}
    </WorkGateContext.Provider>
  );
}

export function useWorkGate(): WorkGateValue {
  return useContext(WorkGateContext);
}
