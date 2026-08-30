"""Google ADK 2.0 workflow nodes — deterministic stages call backend services directly."""

from __future__ import annotations

from google.adk.workflow import node

from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.google_adk.container import get_service_container
from app.google_adk.context import get_run_context
from app.intelligence import RepositoryEmptyError, RepositoryNotReadyError
from app.models.agent_event import AgentEventType
from app.models.agent_state import OrchestrationStatus
from app.models.run import RunStatus
from app.services.git_finalization_service import RunNotReadyForGitFinalizationError
from app.google_adk.errors import WorkflowPausedForApprovalError
from app.services.human_approval_service import RunNotAwaitingApprovalError
from app.services.regression_test_service import PassedVerificationsRequiredError
from app.services.report_service import RunNotReadyForReportError
from app.services.risk_assessment_service import PatchPlansRequiredError
from app.services.self_correction_service import VerificationFailuresRequiredError
from app.services.verification_service import FixAttemptsRequiredError


def _skipped(stage: OrchestrationStage, *, progress: int, reason: str) -> dict[str, object]:
    _update_stage(stage, progress=progress)
    return {"status": "skipped", "reason": reason}


def _emitter() -> AgentEventEmitter:
    context = get_run_context()
    services = get_service_container()
    return AgentEventEmitter(context.run_id, services.event_repository)


def _update_stage(stage: OrchestrationStage, *, progress: int) -> None:
    context = get_run_context()
    services = get_service_container()
    services.state_repository.update_fields(
        context.run_id,
        status=OrchestrationStatus.RUNNING,
        current_stage=stage.value,
        progress=progress,
    )


@node(name="initialize_run")
def initialize_run() -> dict[str, str]:
    context = get_run_context()
    services = get_service_container()
    services.state_repository.initialize(context.run_id)
    _update_stage(OrchestrationStage.INITIALIZATION, progress=0)
    _emitter().yield_event(
        WorkflowEvent(
            event_type=AgentEventType.RUN_CREATED,
            stage=OrchestrationStage.INITIALIZATION,
            payload={"run_id": context.run_id},
        ),
    )
    return {"status": "initialized", "run_id": context.run_id}


@node(name="clone_repository")
def clone_repository() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    if context.skip_clone:
        return {"status": "skipped"}

    _update_stage(OrchestrationStage.CLONING, progress=10)
    emitter = _emitter()
    emitter.yield_event(
        WorkflowEvent(
            event_type=AgentEventType.CLONE_STARTED,
            stage=OrchestrationStage.CLONING,
            payload={"branch": context.branch},
        ),
    )

    run = services.run_repository.get_by_id_for_user(context.run_id, context.user_id)
    if run is None or run.repository_id is None:
        raise RuntimeError("Run has no linked repository for cloning")

    result = services.git_service.clone_run_repository(
        context.user_id,
        context.run_id,
        branch=context.branch,
    )
    if not result.success:
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.CLONE_FAILED,
                stage=OrchestrationStage.CLONING,
                status="failed",
                message=result.message,
            ),
        )
        raise RuntimeError(result.message or "Repository clone failed")

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
    return {"status": "cloned", "branch": result.branch}


@node(name="analyze_project_intelligence")
def analyze_project_intelligence() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.PROJECT_INTELLIGENCE, progress=30)
    emitter = _emitter()
    emitter.yield_event(
        WorkflowEvent(
            event_type=AgentEventType.PROJECT_ANALYSIS_STARTED,
            stage=OrchestrationStage.PROJECT_INTELLIGENCE,
        ),
    )
    try:
        intelligence = services.intelligence_service.analyze_run(context.user_id, context.run_id)
    except (RepositoryNotReadyError, RepositoryEmptyError) as exc:
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PROJECT_ANALYSIS_FAILED,
                stage=OrchestrationStage.PROJECT_INTELLIGENCE,
                status="failed",
                message=exc.message,
            ),
        )
        raise RuntimeError(exc.message) from exc

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
    return {"status": "analyzed", "frameworks": intelligence.intelligence.frameworks}


@node(name="run_diagnostics")
def run_diagnostics() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.DIAGNOSTICS, progress=55)
    agents = list(context.agents) if context.agents else None
    result = services.diagnostic_agent_service.run_agents(
        context.user_id,
        context.run_id,
        agents=agents,
    )
    return {"status": "completed", "findings_count": result.finding_count}


@node(name="correlate_findings")
def correlate_findings() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.ISSUE_CORRELATION, progress=60)
    result = services.issue_correlation_service.correlate_run(context.user_id, context.run_id)
    return {
        "status": "completed",
        "groups_created": result.issue_group_count,
        "group_count": result.issue_group_count,
    }


@node(name="assess_risk")
def assess_risk() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.RISK_ASSESSMENT, progress=70)
    try:
        result = services.risk_assessment_service.assess_run(context.user_id, context.run_id)
    except PatchPlansRequiredError:
        return _skipped(
            OrchestrationStage.RISK_ASSESSMENT,
            progress=70,
            reason="no_patch_plans",
        )
    return {
        "status": "completed",
        "decisions": result.decision_count,
    }


@node(name="gate_risk_approval")
def gate_risk_approval() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    approval_service = services.human_approval_service

    if not approval_service.has_blocking_risk_gate_approval(context.run_id):
        return {"status": "passed"}

    _update_stage(OrchestrationStage.HUMAN_APPROVAL, progress=72)
    try:
        approval_service.prepare_approvals(context.user_id, context.run_id)
    except RunNotAwaitingApprovalError:
        pass

    if not approval_service.has_blocking_risk_gate_approval(context.run_id):
        services.state_repository.update_fields(
            context.run_id,
            approval_required=False,
        )
        return {"status": "passed"}

    services.state_repository.update_fields(
        context.run_id,
        approval_required=True,
    )
    services.run_repository.update_status(
        context.run_id,
        context.user_id,
        RunStatus.AWAITING_APPROVAL,
    )
    raise WorkflowPausedForApprovalError(
        "Human approval is required before applying fixes",
        OrchestrationStage.HUMAN_APPROVAL,
    )


@node(name="verify_fixes")
def verify_fixes() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.VERIFICATION, progress=80)
    try:
        result = services.verification_service.verify_run(context.user_id, context.run_id)
    except FixAttemptsRequiredError:
        return _skipped(
            OrchestrationStage.VERIFICATION,
            progress=80,
            reason="no_fix_attempts",
        )
    return {
        "status": result.run_status,
        "results": result.result_count,
    }


@node(name="self_correct")
def self_correct() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.SELF_CORRECTION, progress=82)
    try:
        result = services.self_correction_service.correct_run(context.user_id, context.run_id)
    except VerificationFailuresRequiredError:
        return _skipped(
            OrchestrationStage.SELF_CORRECTION,
            progress=82,
            reason="no_failed_verifications",
        )
    return {
        "status": result.run_status,
        "cycles": result.cycle_count,
    }


@node(name="run_regression_tests")
def run_regression_tests() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.REGRESSION_TESTING, progress=85)
    try:
        result = services.regression_test_service.run_regression_tests(
            context.user_id,
            context.run_id,
        )
    except PassedVerificationsRequiredError:
        return _skipped(
            OrchestrationStage.REGRESSION_TESTING,
            progress=85,
            reason="no_passed_verifications",
        )
    return {
        "status": result.run_status,
        "results": result.result_count,
    }


@node(name="prepare_human_approvals")
def prepare_human_approvals() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.HUMAN_APPROVAL, progress=88)
    try:
        result = services.human_approval_service.prepare_approvals(context.user_id, context.run_id)
    except RunNotAwaitingApprovalError:
        return _skipped(
            OrchestrationStage.HUMAN_APPROVAL,
            progress=88,
            reason="not_awaiting_approval",
        )
    return {
        "status": "completed",
        "approvals_created": result.approval_count,
        "approval_ids": [approval.approval_id for approval in result.approvals],
    }


@node(name="capture_memory")
def capture_memory() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.MEMORY, progress=92)
    result = services.memory_service.capture_run_memory(context.user_id, context.run_id)
    return {
        "status": "completed",
        "memories_captured": result.memory_count,
    }


@node(name="finalize_git")
def finalize_git() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.GIT_FINALIZATION, progress=95)
    try:
        result = services.git_finalization_service.finalize_run(context.user_id, context.run_id)
    except RunNotReadyForGitFinalizationError as exc:
        return _skipped(
            OrchestrationStage.GIT_FINALIZATION,
            progress=95,
            reason=exc.message,
        )
    return {
        "status": result.run_status,
        "operation_id": result.operation.git_operation_id,
    }


@node(name="generate_report")
def generate_report() -> dict[str, object]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.REPORTING, progress=98)
    run = services.run_repository.get_by_id_for_user(context.run_id, context.user_id)
    if run is not None and run.status != RunStatus.REPORTING:
        services.run_repository.update_status(
            context.run_id,
            context.user_id,
            RunStatus.REPORTING,
        )
    try:
        result = services.report_service.generate_run_report(
            context.user_id,
            context.run_id,
            allow_without_git=True,
        )
    except RunNotReadyForReportError as exc:
        return _skipped(
            OrchestrationStage.REPORTING,
            progress=98,
            reason=exc.message,
        )
    return {
        "status": result.run_status,
        "report_id": result.report.report_id,
    }


@node(name="finalize_run")
def finalize_run() -> dict[str, str]:
    context = get_run_context()
    services = get_service_container()
    _update_stage(OrchestrationStage.FINALIZATION, progress=100)

    if services.report_service.get_run_report(context.user_id, context.run_id) is None:
        try:
            services.report_service.generate_run_report(
                context.user_id,
                context.run_id,
                allow_without_git=True,
            )
        except RunNotReadyForReportError:
            pass

    services.state_repository.update_fields(
        context.run_id,
        status=OrchestrationStatus.COMPLETED,
        current_stage=OrchestrationStage.FINALIZATION.value,
        progress=100,
    )
    _emitter().yield_event(
        WorkflowEvent(
            event_type=AgentEventType.RUN_COMPLETED,
            stage=OrchestrationStage.FINALIZATION,
            payload={"run_id": context.run_id},
        ),
    )
    return {"status": "completed"}
