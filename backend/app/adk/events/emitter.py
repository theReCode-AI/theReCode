from dataclasses import dataclass, field
from typing import Any

from app.adk.workflows.stages import OrchestrationStage
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.models.agent_event import AgentEvent, AgentEventType


@dataclass
class WorkflowEvent:
    """ADK 2.0-aligned workflow event yielded by orchestration nodes."""

    event_type: AgentEventType
    stage: OrchestrationStage
    agent: str | None = None
    tool: str | None = None
    status: str = "ok"
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class AgentEventEmitter:
    """Persist workflow events and expose ADK-style event yields."""

    def __init__(self, run_id: str, event_repository: AgentEventRepository) -> None:
        self._run_id = run_id
        self._event_repository = event_repository

    def emit(self, workflow_event: WorkflowEvent) -> AgentEvent:
        return self._event_repository.create_event(
            run_id=self._run_id,
            event_type=workflow_event.event_type,
            stage=workflow_event.stage.value,
            agent=workflow_event.agent,
            tool=workflow_event.tool,
            status=workflow_event.status,
            message=workflow_event.message,
            payload=workflow_event.payload,
        )

    def yield_event(self, workflow_event: WorkflowEvent) -> WorkflowEvent:
        self.emit(workflow_event)
        return workflow_event
