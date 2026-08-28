import type { RunStreamConnectionStatus } from "@/stores/runLiveStore";

const LABELS: Record<RunStreamConnectionStatus, string> = {
  idle: "Idle",
  connecting: "Connecting",
  open: "Live",
  closed: "Completed",
  error: "Reconnecting soon",
};

interface LiveConnectionBadgeProps {
  status: RunStreamConnectionStatus;
}

export function LiveConnectionBadge({ status }: LiveConnectionBadgeProps) {
  return (
    <span className={`live-badge live-${status}`} data-testid="live-connection-badge">
      {LABELS[status]}
    </span>
  );
}
