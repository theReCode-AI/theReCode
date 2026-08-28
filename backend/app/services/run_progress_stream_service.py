import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from app.api.sse import format_sse_event
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.run import RunStatus
from app.schemas.orchestration import (
    AgentEventResponse,
    RunAgentStateResponse,
    RunProgressSnapshot,
)
from app.schemas.run import RunResponse

TERMINAL_RUN_STATUSES = {
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
}


class RunProgressStreamService:
    """Streams run progress updates over Server-Sent Events."""

    def __init__(
        self,
        run_repository: RunRepository,
        event_repository: AgentEventRepository,
        state_repository: AgentStateRepository,
        *,
        poll_interval_seconds: float = 1.5,
        heartbeat_every_polls: int = 4,
        terminal_grace_polls: int = 2,
    ) -> None:
        self._run_repository = run_repository
        self._event_repository = event_repository
        self._state_repository = state_repository
        self._poll_interval_seconds = poll_interval_seconds
        self._heartbeat_every_polls = heartbeat_every_polls
        self._terminal_grace_polls = terminal_grace_polls

    async def stream_run_progress(self, user_id: str, run_id: str) -> AsyncIterator[str]:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        last_event_at: datetime | None = None
        last_run_updated_at = run.updated_at
        last_state_updated_at: datetime | None = None
        terminal_polls = 0
        poll_count = 0

        state = self._state_repository.get_by_run(run_id)
        events = self._event_repository.list_by_run(run_id)
        if events:
            last_event_at = events[-1].created_at
        if state is not None:
            last_state_updated_at = state.updated_at

        snapshot = RunProgressSnapshot(
            run=RunResponse.model_validate(run.model_dump()),
            state=RunAgentStateResponse.model_validate(state.model_dump())
            if state is not None
            else None,
            events=[AgentEventResponse.model_validate(event.model_dump()) for event in events],
        )
        yield format_sse_event("snapshot", snapshot.model_dump(mode="json"))

        while True:
            await asyncio.sleep(self._poll_interval_seconds)
            poll_count += 1

            current_run = self._run_repository.get_by_id_for_user(run_id, user_id)
            if current_run is None:
                raise RunNotFoundError(run_id)

            if current_run.updated_at != last_run_updated_at:
                last_run_updated_at = current_run.updated_at
                yield format_sse_event(
                    "run_update",
                    RunResponse.model_validate(current_run.model_dump()).model_dump(mode="json"),
                )

            new_events = self._event_repository.list_by_run_after(run_id, last_event_at)
            for event in new_events:
                last_event_at = event.created_at
                yield format_sse_event(
                    "agent_event",
                    AgentEventResponse.model_validate(event.model_dump()).model_dump(mode="json"),
                    event_id=event.id,
                )

            current_state = self._state_repository.get_by_run(run_id)
            if current_state is not None and current_state.updated_at != last_state_updated_at:
                last_state_updated_at = current_state.updated_at
                yield format_sse_event(
                    "state_update",
                    RunAgentStateResponse.model_validate(
                        current_state.model_dump(),
                    ).model_dump(mode="json"),
                )

            if poll_count % self._heartbeat_every_polls == 0:
                yield format_sse_event(
                    "heartbeat",
                    {"timestamp": datetime.now(UTC).isoformat()},
                )

            if current_run.status in TERMINAL_RUN_STATUSES:
                terminal_polls += 1
                if terminal_polls >= self._terminal_grace_polls:
                    yield format_sse_event(
                        "complete",
                        {
                            "run_id": run_id,
                            "status": current_run.status.value,
                            "reason": "terminal_status",
                        },
                    )
                    break
