import { Badge } from "flowbite-react";

import type { RunStatus } from "@/types/run";
import { formatStatus } from "@/utils/runStages";

const STATUS_COLOR: Record<string, "success" | "failure" | "warning" | "info" | "gray"> = {
  COMPLETED: "success",
  FAILED: "failure",
  CANCELLED: "failure",
  AWAITING_APPROVAL: "warning",
  SELF_CORRECTING: "warning",
};

interface RunStatusBadgeProps {
  status: RunStatus | string;
}

export function RunStatusBadge({ status }: RunStatusBadgeProps) {
  const color = STATUS_COLOR[status] ?? "info";
  return <Badge color={color}>{formatStatus(status)}</Badge>;
}
