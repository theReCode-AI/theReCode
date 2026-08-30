import { Badge } from "flowbite-react";

import type { RunStreamConnectionStatus } from "@/stores/runLiveStore";

const LABELS: Record<RunStreamConnectionStatus, string> = {
  idle: "Idle",
  connecting: "Connecting",
  open: "Live",
  closed: "Completed",
  error: "Reconnecting soon",
};

const STATUS_COLOR: Record<RunStreamConnectionStatus, "success" | "info" | "gray" | "failure"> = {
  idle: "gray",
  connecting: "info",
  open: "success",
  closed: "gray",
  error: "failure",
};

interface LiveConnectionBadgeProps {
  status: RunStreamConnectionStatus;
}

export function LiveConnectionBadge({ status }: LiveConnectionBadgeProps) {
  return (
    <Badge color={STATUS_COLOR[status]} data-testid="live-connection-badge">
      {LABELS[status]}
    </Badge>
  );
}
