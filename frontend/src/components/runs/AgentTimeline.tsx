import type { AgentEvent } from "@/types/run";
import { formatDateTime, formatEventLabel } from "@/utils/runStages";

interface AgentTimelineProps {
  events: AgentEvent[];
}

export function AgentTimeline({ events }: AgentTimelineProps) {
  if (events.length === 0) {
    return <p className="state-message state-empty">No timeline events yet.</p>;
  }

  const sorted = [...events].sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
  );

  return (
    <ol className="agent-timeline" data-testid="agent-timeline">
      {sorted.map((event) => (
        <li key={event.id} className={`timeline-item timeline-${event.status}`}>
          <div className="timeline-marker" />
          <div className="timeline-content">
            <strong>{formatEventLabel(event.event_type)}</strong>
            {event.message ? <p>{event.message}</p> : null}
            <small>
              {formatDateTime(event.created_at)}
              {event.agent ? ` · ${event.agent}` : ""}
            </small>
          </div>
        </li>
      ))}
    </ol>
  );
}
