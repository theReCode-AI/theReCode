from datetime import UTC, datetime

from bson import ObjectId

from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.models.agent_event import AgentEvent, AgentEventType
from app.models.agent_state import OrchestrationStatus, RunAgentState


class InMemoryAgentEventRepository(AgentEventRepository):
    def __init__(self) -> None:
        self._events: list[AgentEvent] = []

    def append(self, event: AgentEvent) -> AgentEvent:
        self._events.append(event)
        return event

    def list_by_run(self, run_id: str) -> list[AgentEvent]:
        return [event for event in self._events if event.run_id == run_id]

    def list_by_run_after(self, run_id: str, after_created_at: datetime | None) -> list[AgentEvent]:
        events = self.list_by_run(run_id)
        if after_created_at is None:
            return events
        return [event for event in events if event.created_at > after_created_at]

    def create_event(
        self,
        run_id: str,
        event_type: AgentEventType,
        stage: str,
        *,
        agent: str | None = None,
        tool: str | None = None,
        status: str = "ok",
        message: str | None = None,
        payload: dict | None = None,
    ) -> AgentEvent:
        now = datetime.now(UTC)
        event = AgentEvent(
            _id=str(ObjectId()),
            run_id=run_id,
            event_type=event_type,
            stage=stage,
            agent=agent,
            tool=tool,
            status=status,
            message=message,
            payload=payload or {},
            created_at=now,
        )
        return self.append(event)


class InMemoryAgentStateRepository(AgentStateRepository):
    def __init__(self) -> None:
        self._states: dict[str, RunAgentState] = {}

    def get_by_run(self, run_id: str) -> RunAgentState | None:
        return self._states.get(run_id)

    def upsert(self, state: RunAgentState) -> RunAgentState:
        self._states[state.run_id] = state
        return state

    def initialize(self, run_id: str) -> RunAgentState:
        now = datetime.now(UTC)
        state = RunAgentState(
            _id=str(ObjectId()),
            run_id=run_id,
            status=OrchestrationStatus.PENDING,
            progress=0,
            updated_at=now,
            created_at=now,
        )
        return self.upsert(state)

    def update_fields(self, run_id: str, **fields: object) -> RunAgentState | None:
        existing = self.get_by_run(run_id)
        if existing is None:
            return None

        updated = existing.model_copy(
            update={**fields, "updated_at": datetime.now(UTC)},
        )
        return self.upsert(updated)
