from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.intelligence import RepositoryEmptyError, RepositoryNotReadyError
from app.models.agent_event import AgentEventType
from app.models.agent_state import OrchestrationStatus, RunAgentState
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.git_service import GitService
from app.services.project_intelligence_service import ProjectIntelligenceService
from app.services.run_service import RunService

logger = get_logger(__name__)


class OrchestrationError(Exception):
    def __init__(self, message: str, stage: OrchestrationStage) -> None:
        self.message = message
        self.stage = stage
        super().__init__(message)


class RootOrchestrator:
    """ADK-style root orchestrator for baseline autonomous run lifecycle."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        git_service: GitService,
        intelligence_service: ProjectIntelligenceService,
        diagnostic_agent_service: DiagnosticAgentService,
        event_repository: AgentEventRepository,
        state_repository: AgentStateRepository,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._git_service = git_service
        self._intelligence_service = intelligence_service
        self._diagnostic_agent_service = diagnostic_agent_service
        self._event_repository = event_repository
        self._state_repository = state_repository

    def execute(
        self,
        user_id: str,
        run_id: str,
        *,
        branch: str | None = None,
        skip_clone: bool = False,
        agents: list[DiagnosticAgentName] | None = None,
    ) -> RunAgentState:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        emitter = AgentEventEmitter(run_id, self._event_repository)
        self._state_repository.initialize(run_id)
        self._update_state(
            run_id,
            status=OrchestrationStatus.RUNNING,
            current_stage=OrchestrationStage.INITIALIZATION.value,
            progress=0,
        )

        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.RUN_CREATED,
                stage=OrchestrationStage.INITIALIZATION,
                payload={"run_id": run_id},
            ),
        )

        try:
            if not skip_clone:
                self._run_clone_stage(user_id, run_id, branch, emitter)
            else:
                self._ensure_repository_ready(user_id, run_id)

            self._run_intelligence_stage(user_id, run_id, emitter)
            findings_count = self._run_diagnostics_stage(
                user_id,
                run_id,
                emitter,
                agents,
            )
            self._run_finalization_stage(run_id, emitter, findings_count)
        except OrchestrationError as exc:
            self._handle_failure(run_id, user_id, emitter, exc)
        except Exception as exc:
            self._handle_failure(
                run_id,
                user_id,
                emitter,
                OrchestrationError(str(exc), OrchestrationStage.FINALIZATION),
            )

        final_state = self._state_repository.get_by_run(run_id)
        if final_state is None:
            raise RunNotFoundError(run_id)
        return final_state

    def _run_clone_stage(
        self,
        user_id: str,
        run_id: str,
        branch: str | None,
        emitter: AgentEventEmitter,
    ) -> None:
        self._update_state(
            run_id,
            current_stage=OrchestrationStage.CLONING.value,
            progress=10,
        )
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.CLONE_STARTED,
                stage=OrchestrationStage.CLONING,
                payload={"branch": branch},
            ),
        )

        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None or run.repository_id is None:
            raise OrchestrationError(
                "Run has no linked repository for cloning",
                OrchestrationStage.CLONING,
            )

        result = self._git_service.clone_run_repository(user_id, run_id, branch=branch)
        if not result.success:
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.CLONE_FAILED,
                    stage=OrchestrationStage.CLONING,
                    status="failed",
                    message=result.message,
                ),
            )
            raise OrchestrationError(
                result.message or "Repository clone failed",
                OrchestrationStage.CLONING,
            )

        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.CLONE_COMPLETED,
                stage=OrchestrationStage.CLONING,
                payload={
                    "destination": str(result.destination),
                    "branch": result.branch,
                    "commit_sha": result.commit_sha,
                },
            ),
        )
        self._mark_stage_complete(run_id, OrchestrationStage.CLONING.value, progress=25)

    def _run_intelligence_stage(
        self,
        user_id: str,
        run_id: str,
        emitter: AgentEventEmitter,
    ) -> None:
        self._update_state(
            run_id,
            current_stage=OrchestrationStage.PROJECT_INTELLIGENCE.value,
            progress=30,
        )
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PROJECT_ANALYSIS_STARTED,
                stage=OrchestrationStage.PROJECT_INTELLIGENCE,
            ),
        )

        try:
            intelligence = self._intelligence_service.analyze_run(user_id, run_id)
        except (RepositoryNotReadyError, RepositoryEmptyError) as exc:
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.PROJECT_ANALYSIS_FAILED,
                    stage=OrchestrationStage.PROJECT_INTELLIGENCE,
                    status="failed",
                    message=exc.message,
                ),
            )
            raise OrchestrationError(exc.message, OrchestrationStage.PROJECT_INTELLIGENCE) from exc

        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PROJECT_ANALYSIS_COMPLETED,
                stage=OrchestrationStage.PROJECT_INTELLIGENCE,
                payload={
                    "package_manager": intelligence.intelligence.package_manager.value,
                    "frameworks": intelligence.intelligence.frameworks,
                },
            ),
        )
        self._mark_stage_complete(
            run_id,
            OrchestrationStage.PROJECT_INTELLIGENCE.value,
            progress=50,
        )

    def _run_diagnostics_stage(
        self,
        user_id: str,
        run_id: str,
        emitter: AgentEventEmitter,
        agents: list[DiagnosticAgentName] | None,
    ) -> int:
        self._update_state(
            run_id,
            current_stage=OrchestrationStage.DIAGNOSTICS.value,
            progress=55,
        )
        self._run_repository.update_status(run_id, user_id, RunStatus.DIAGNOSING)

        selected_agents = agents or list(DiagnosticAgentName)
        total_agents = len(selected_agents)
        findings_count = 0

        for index, agent_name in enumerate(selected_agents, start=1):
            self._update_state(run_id, current_agent=agent_name.value)
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.AGENT_STARTED,
                    stage=OrchestrationStage.DIAGNOSTICS,
                    agent=agent_name.value,
                ),
            )

            try:
                result = self._diagnostic_agent_service.execute_agent(user_id, run_id, agent_name)
            except Exception as exc:
                emitter.yield_event(
                    WorkflowEvent(
                        event_type=AgentEventType.AGENT_FAILED,
                        stage=OrchestrationStage.DIAGNOSTICS,
                        agent=agent_name.value,
                        status="failed",
                        message=str(exc),
                    ),
                )
                raise OrchestrationError(str(exc), OrchestrationStage.DIAGNOSTICS) from exc

            findings_count += len(result.findings)
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.AGENT_COMPLETED,
                    stage=OrchestrationStage.DIAGNOSTICS,
                    agent=agent_name.value,
                    payload={"finding_count": len(result.findings)},
                ),
            )
            self._mark_agent_complete(run_id, agent_name.value)
            progress = 55 + int((index / total_agents) * 35)
            self._update_state(run_id, progress=progress)

        if findings_count > 0:
            emitter.yield_event(
                WorkflowEvent(
                    event_type=AgentEventType.FINDING_CREATED,
                    stage=OrchestrationStage.DIAGNOSTICS,
                    payload={"finding_count": findings_count},
                ),
            )

        self._mark_stage_complete(run_id, OrchestrationStage.DIAGNOSTICS.value, progress=90)
        return findings_count

    def _run_finalization_stage(
        self,
        run_id: str,
        emitter: AgentEventEmitter,
        findings_count: int,
    ) -> None:
        self._update_state(
            run_id,
            current_stage=OrchestrationStage.FINALIZATION.value,
            current_agent=None,
            progress=95,
        )
        self._mark_stage_complete(run_id, OrchestrationStage.FINALIZATION.value, progress=100)
        self._update_state(
            run_id,
            status=OrchestrationStatus.COMPLETED,
            current_stage=OrchestrationStage.FINALIZATION.value,
            progress=100,
        )
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.RUN_COMPLETED,
                stage=OrchestrationStage.FINALIZATION,
                payload={"finding_count": findings_count},
            ),
        )

    def _handle_failure(
        self,
        run_id: str,
        user_id: str,
        emitter: AgentEventEmitter,
        error: OrchestrationError,
    ) -> None:
        self._run_repository.update_status(run_id, user_id, RunStatus.FAILED)
        self._update_state(
            run_id,
            status=OrchestrationStatus.FAILED,
            current_stage=error.stage.value,
            error_message=error.message,
        )
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.RUN_FAILED,
                stage=error.stage,
                status="failed",
                message=error.message,
            ),
        )
        logger.error(
            "Run orchestration failed",
            extra={
                "run_id": run_id,
                "stage": error.stage.value,
                "error_message": error.message,
                "stage_name": "root_orchestrator",
            },
        )

    def _ensure_repository_ready(self, user_id: str, run_id: str) -> None:
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        repository_path = workspace.repository
        if not repository_path.exists() or not any(repository_path.iterdir()):
            raise OrchestrationError(
                "Repository must be cloned before orchestration",
                OrchestrationStage.CLONING,
            )

    def _update_state(self, run_id: str, **fields: object) -> RunAgentState:
        updated = self._state_repository.update_fields(run_id, **fields)
        if updated is None:
            return self._state_repository.initialize(run_id)
        return updated

    def _mark_stage_complete(self, run_id: str, stage: str, *, progress: int) -> None:
        state = self._state_repository.get_by_run(run_id)
        if state is None:
            return
        completed_stages = list(state.completed_stages)
        if stage not in completed_stages:
            completed_stages.append(stage)
        self._update_state(
            run_id,
            completed_stages=completed_stages,
            progress=progress,
        )

    def _mark_agent_complete(self, run_id: str, agent: str) -> None:
        state = self._state_repository.get_by_run(run_id)
        if state is None:
            return
        completed_agents = list(state.completed_agents)
        if agent not in completed_agents:
            completed_agents.append(agent)
        self._update_state(run_id, completed_agents=completed_agents)
