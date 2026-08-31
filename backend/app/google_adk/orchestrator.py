"""Google ADK 2.0 root orchestrator — replaces the custom RootOrchestrator."""

from __future__ import annotations

import logging

from google.adk.apps.app import App
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.core.config import Settings
from app.db.repositories.run_repository import RunNotFoundError
from app.google_adk.bootstrap import bootstrap_google_genai, ensure_google_adk_configured
from app.google_adk.container import (
    ServiceContainer,
    clear_service_container,
    set_service_container,
)
from app.google_adk.context import RunExecutionContext, clear_run_context, set_run_context
from app.google_adk.errors import WorkflowPausedForApprovalError
from app.google_adk.workflow_builder import (
    build_therecode_workflow,
    build_post_risk_approval_workflow,
    build_replan_after_feedback_workflow,
)
from app.models.agent_event import AgentEventType
from app.models.agent_state import OrchestrationStatus, RunAgentState
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.workspace.exceptions import WorkspaceNotFoundError

logger = logging.getLogger(__name__)


class GoogleAdkOrchestrationError(Exception):
    def __init__(self, message: str, stage: OrchestrationStage) -> None:
        self.message = message
        self.stage = stage
        super().__init__(message)


class GoogleAdkOrchestrator:
    """Runs the full theReCode lifecycle through a Google ADK 2.0 Workflow."""

    def __init__(
        self,
        settings: Settings,
        services: ServiceContainer,
    ) -> None:
        self._settings = settings
        self._services = services

    async def execute(
        self,
        user_id: str,
        run_id: str,
        *,
        branch: str | None = None,
        skip_clone: bool = False,
        agents: list[DiagnosticAgentName] | None = None,
        resume_after_approval: bool = False,
        replan_after_feedback: bool = False,
    ) -> RunAgentState:
        if self._services.run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        api_key = None
        if self._services.gemini_credential_service is not None:
            api_key = self._services.gemini_credential_service.try_get_api_key(user_id)

        ensure_google_adk_configured(self._settings, api_key=api_key)
        bootstrap_google_genai(self._settings, api_key=api_key)

        if resume_after_approval:
            self._services.state_repository.update_fields(
                run_id,
                approval_required=False,
                current_stage=OrchestrationStage.CODE_FIXING.value,
            )
            self._services.run_repository.update_status(run_id, user_id, RunStatus.FIXING)
        elif replan_after_feedback:
            self._services.state_repository.update_fields(
                run_id,
                approval_required=False,
                current_stage=OrchestrationStage.FIX_PLANNING.value,
            )
            self._services.run_repository.update_status(run_id, user_id, RunStatus.PLANNING)

        skip_clone_effective = skip_clone or resume_after_approval
        if replan_after_feedback:
            skip_clone_effective = self._workspace_ready(user_id, run_id)

        run_context = RunExecutionContext(
            user_id=user_id,
            run_id=run_id,
            branch=branch,
            skip_clone=skip_clone_effective,
            agents=tuple(agents) if agents else None,
        )
        set_run_context(run_context)
        set_service_container(self._services)

        emitter = AgentEventEmitter(run_id, self._services.event_repository)
        try:
            if resume_after_approval:
                await self._run_workflow_async(
                    user_id=user_id,
                    run_id=run_id,
                    phase="post_risk",
                )
            else:
                await self._run_workflow_async(
                    user_id=user_id,
                    run_id=run_id,
                    phase="replan" if replan_after_feedback else "pre_risk",
                )
                if self._is_awaiting_approval(run_id, user_id):
                    self._handle_pause(
                        run_id,
                        user_id,
                        emitter,
                        WorkflowPausedForApprovalError(
                            "Human approval is required before applying fixes",
                            OrchestrationStage.HUMAN_APPROVAL,
                        ),
                    )
                else:
                    await self._run_workflow_async(
                        user_id=user_id,
                        run_id=run_id,
                        phase="post_risk",
                    )
        except WorkflowPausedForApprovalError as exc:
            self._handle_pause(run_id, user_id, emitter, exc)
        except Exception as exc:
            self._handle_failure(run_id, user_id, emitter, exc)
            raise
        finally:
            clear_run_context()
            clear_service_container()

        final_state = self._services.state_repository.get_by_run(run_id)
        if final_state is None:
            raise RunNotFoundError(run_id)
        return final_state

    def _is_awaiting_approval(self, run_id: str, user_id: str) -> bool:
        run = self._services.run_repository.get_by_id_for_user(run_id, user_id)
        return run is not None and run.status == RunStatus.AWAITING_APPROVAL

    async def _run_workflow_async(
        self,
        *,
        user_id: str,
        run_id: str,
        phase: str,
    ) -> None:
        if phase == "replan":
            workflow = build_replan_after_feedback_workflow(model=self._settings.gemini_model)
            prompt = (
                "Replan the autonomous run using the human reviewer's feedback. "
                "Create updated patch plans and reassess risk."
            )
            session_id = f"{run_id}-replan"
        elif phase == "post_risk":
            workflow = build_post_risk_approval_workflow(model=self._settings.gemini_model)
            prompt = (
                "Continue the autonomous run from code fixing through finalization."
            )
            session_id = f"{run_id}-post-risk"
        else:
            workflow = build_therecode_workflow(model=self._settings.gemini_model)
            prompt = (
                "Execute repository analysis through risk assessment for this autonomous run. "
                "Follow the workflow stages in order and use tools where required."
            )
            session_id = f"{run_id}-pre-risk"

        app = App(name=self._settings.google_adk_app_name, root_agent=workflow)
        session_service = InMemorySessionService()
        runner = Runner(
            app=app,
            session_service=session_service,
            auto_create_session=True,
        )

        await session_service.create_session(
            app_name=self._settings.google_adk_app_name,
            user_id=user_id,
            session_id=session_id,
        )

        message = types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        )

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message,
        ):
            logger.debug(
                "ADK workflow event",
                extra={"run_id": run_id, "phase": phase, "author": event.author},
            )

    def _handle_pause(
        self,
        run_id: str,
        user_id: str,
        emitter: AgentEventEmitter,
        exc: WorkflowPausedForApprovalError,
    ) -> None:
        from app.models.run import RunStatus

        self._services.state_repository.update_fields(
            run_id,
            status=OrchestrationStatus.RUNNING,
            current_stage=exc.stage.value,
            approval_required=True,
            error_message=None,
        )
        self._services.run_repository.update_status(run_id, user_id, RunStatus.AWAITING_APPROVAL)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.APPROVAL_REQUIRED,
                stage=exc.stage,
                agent="human_approval_agent",
                message=exc.message,
            ),
        )
        logger.info(
            "Run paused for human approval",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "stage": exc.stage.value,
            },
        )

    def _handle_failure(
        self,
        run_id: str,
        user_id: str,
        emitter: AgentEventEmitter,
        exc: Exception,
    ) -> None:
        from app.models.run import RunStatus

        stage = OrchestrationStage.FINALIZATION
        if isinstance(exc, GoogleAdkOrchestrationError):
            stage = exc.stage

        self._services.state_repository.update_fields(
            run_id,
            status=OrchestrationStatus.FAILED,
            current_stage=stage.value,
            error_message=str(exc),
        )
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.RUN_FAILED,
                stage=stage,
                status="failed",
                message=str(exc),
            ),
        )
        self._services.run_repository.update_status(run_id, user_id, RunStatus.FAILED)

    def _workspace_ready(self, user_id: str, run_id: str) -> bool:
        try:
            workspace = self._services.run_service.get_workspace_for_run(user_id, run_id)
        except WorkspaceNotFoundError:
            return False
        repository = workspace.repository
        if not repository.is_dir():
            return False
        return any(repository.iterdir())
