import type { RunStatus } from "@/types/run";
import { formatStatus } from "@/utils/runStages";

const STATUS_CLASS: Record<string, string> = {
  COMPLETED: "status-completed",
  FAILED: "status-failed",
  CANCELLED: "status-cancelled",
  AWAITING_APPROVAL: "status-warning",
  SELF_CORRECTING: "status-warning",
};

interface RunStatusBadgeProps {
  status: RunStatus | string;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  const className = STATUS_CLASS[status] ?? "status-active";
  return <span className={`status-badge ${className}`}>{formatStatus(status)}</span>;
}
