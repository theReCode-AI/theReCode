from app.adk.workflows.root_orchestrator import RootOrchestrator
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.google_adk.orchestrator import GoogleAdkOrchestrator
from app.models.finding_enums import DiagnosticAgentName
from app.schemas.orchestration import (
    AgentEventResponse,
    RunAgentStateResponse,
    RunOrchestrationResponse,
)


class AgentStateNotFoundError(Exception):
    def __init__(self, message: str = "Orchestration state is not available for this run") -> None:
        self.message = message
        super().__init__(message)


class OrchestrationService:
    """Facade for Google ADK orchestrator execution and observability."""

    def __init__(
        self,
        run_repository: RunRepository,
        orchestrator: GoogleAdkOrchestrator | RootOrchestrator,
        event_repository: AgentEventRepository,
        state_repository: AgentStateRepository,
    ) -> None:
        self._run_repository = run_repository
        self._orchestrator = orchestrator
        self._event_repository = event_repository
        self._state_repository = state_repository

    async def execute_run(
        self,
        user_id: str,
        run_id: str,
        *,
        branch: str | None = None,
        skip_clone: bool = False,
        agents: list[DiagnosticAgentName] | None = None,
        resume_after_approval: bool = False,
    ) -> RunOrchestrationResponse:
        if isinstance(self._orchestrator, GoogleAdkOrchestrator):
            state = await self._orchestrator.execute(
                user_id,
                run_id,
                branch=branch,
                skip_clone=skip_clone,
                agents=agents,
                resume_after_approval=resume_after_approval,
            )
        else:
            state = self._orchestrator.execute(
                user_id,
                run_id,
                branch=branch,
                skip_clone=skip_clone,
                agents=agents,
            )
        events = self._event_repository.list_by_run(run_id)
        return RunOrchestrationResponse(
            run_id=run_id,
            state=RunAgentStateResponse.model_validate(state.model_dump()),
            event_count=len(events),
        )

    def list_events(self, user_id: str, run_id: str) -> list[AgentEventResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        events = self._event_repository.list_by_run(run_id)
        return [AgentEventResponse.model_validate(event.model_dump()) for event in events]

    def get_state(self, user_id: str, run_id: str) -> RunAgentStateResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        state = self._state_repository.get_by_run(run_id)
        if state is None:
            raise AgentStateNotFoundError()

        return RunAgentStateResponse.model_validate(state.model_dump())
