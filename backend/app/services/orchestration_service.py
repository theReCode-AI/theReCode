from app.adk.workflows.root_orchestrator import RootOrchestrator
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.google_adk.orchestrator import GoogleAdkOrchestrator
from app.models.agent_state import OrchestrationStatus
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.schemas.orchestration import (
    AgentEventResponse,
    RunAgentStateResponse,
    RunOrchestrationResponse,
)


class AgentStateNotFoundError(Exception):
    def __init__(self, message: str = "Orchestration state is not available for this run") -> None:
        self.message = message
        super().__init__(message)


class RunOrchestrationInProgressError(Exception):
    def __init__(
        self,
        message: str = "This run is already executing. Wait for the current pipeline to finish.",
    ) -> None:
        self.message = message
        super().__init__(message)


_ACTIVE_RUN_STATUSES = frozenset(
    {
        "CLONING",
        "ANALYZING",
        "DIAGNOSING",
        "FIXING",
        "VERIFYING",
        "SELF_CORRECTING",
        "PEER_REVIEW",
        "FINAL_REVIEW",
        "PUSHING",
        "REPORTING",
    },
)

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
        replan_after_feedback: bool = False,
    ) -> RunOrchestrationResponse:
        if isinstance(self._orchestrator, GoogleAdkOrchestrator):
            state = await self._orchestrator.execute(
                user_id,
                run_id,
                branch=branch,
                skip_clone=skip_clone,
                agents=agents,
                resume_after_approval=resume_after_approval,
                replan_after_feedback=replan_after_feedback,
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

    def ensure_can_execute(self, user_id: str, run_id: str) -> None:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        state = self._state_repository.get_by_run(run_id)
        # Only block when the orchestrator is actually running. Standalone steps
        # (e.g. Retry code fixes) can leave run.status=FIXING after the pipeline
        # finished, which previously made Continue/Push permanently unavailable.
        if state is not None and state.status == OrchestrationStatus.RUNNING:
            raise RunOrchestrationInProgressError()
        if (
            state is None
            and run.status.value in _ACTIVE_RUN_STATUSES
            and run.status != RunStatus.FIXING
        ):
            raise RunOrchestrationInProgressError()

        if state is None:
            self._state_repository.initialize(run_id)
        else:
            self._state_repository.update_fields(
                run_id,
                status=OrchestrationStatus.RUNNING,
                error_message=None,
            )

    def build_accepted_response(self, user_id: str, run_id: str) -> RunOrchestrationResponse:
        """Return a snapshot for async execute requests accepted into the background."""
        state = self._state_repository.get_by_run(run_id)
        events = self._event_repository.list_by_run(run_id)
        state_response = (
            RunAgentStateResponse.model_validate(state.model_dump())
            if state is not None
            else None
        )
        if state_response is None:
            raise AgentStateNotFoundError()

        return RunOrchestrationResponse(
            run_id=run_id,
            state=state_response,
            event_count=len(events),
        )
