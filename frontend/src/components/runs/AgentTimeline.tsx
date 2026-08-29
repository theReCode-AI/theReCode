import { Alert } from "flowbite-react";

import type { AgentEvent } from "@/types/run";
import { formatDateTime, formatEventLabel } from "@/utils/runStages";

interface AgentTimelineProps {
  events: AgentEvent[];
}

export function AgentTimeline({ events }: AgentTimelineProps) {
  if (events.length === 0) {
    return (
      <Alert color="info" className="state-message state-empty">
        No timeline events yet.
      </Alert>
    );
  }

  const sorted = [...events].sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
  );

  return (
    <ol className="space-y-4" data-testid="agent-timeline">
      {sorted.map((event) => (
        <li key={event.id} className="flex gap-3">
          <span className="mt-1.5 h-3 w-3 shrink-0 rounded-full bg-blue-600" />
          <div>
            <strong className="text-gray-900">{formatEventLabel(event.event_type)}</strong>
            {event.message ? <p className="mt-1 text-sm text-gray-600">{event.message}</p> : null}
            <small className="mt-1 block text-xs text-gray-500">
              {formatDateTime(event.created_at)}
              {event.agent ? ` · ${event.agent}` : ""}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}
