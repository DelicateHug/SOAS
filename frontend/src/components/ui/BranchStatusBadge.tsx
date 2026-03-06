/**
 * Visual indicator for branch-aware items showing pending change request status.
 */

import type { ChangeRequestItem, ChangeRequestStatus } from "@/types/api";
import type { BranchStatus } from "@/hooks/useBranchAwareList";

const STATUS_LABELS: Record<ChangeRequestStatus, string> = {
  draft: "Draft",
  pushed_to_dev: "In Dev",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
  applied: "Applied",
  withdrawn: "Withdrawn",
};

interface BranchStatusBadgeProps {
  branchStatus: BranchStatus;
  changeRequest?: ChangeRequestItem;
  className?: string;
}

export function BranchStatusBadge({ branchStatus, changeRequest, className = "" }: BranchStatusBadgeProps) {
  if (branchStatus === "unchanged" || !changeRequest) return null;

  const statusLabel = STATUS_LABELS[changeRequest.status] ?? changeRequest.status;

  if (branchStatus === "pending_delete") {
    return (
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/20 text-red-400 ${className}`}>
        Pending Delete · {statusLabel}
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400 ${className}`}>
      Modified · {statusLabel}
    </span>
  );
}

interface PendingCreateBadgeProps {
  changeRequest: ChangeRequestItem;
  className?: string;
}

export function PendingCreateBadge({ changeRequest, className = "" }: PendingCreateBadgeProps) {
  const statusLabel = STATUS_LABELS[changeRequest.status] ?? changeRequest.status;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-500/20 text-green-400 ${className}`}>
      New · {statusLabel}
    </span>
  );
}
