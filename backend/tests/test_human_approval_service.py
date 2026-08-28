from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.adk.risk.policy_engine import RiskPolicyEngine
from app.models.approval_enums import ApprovalStatus, ApprovalTrigger, HumanDecision
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.run import RunStatus
from app.schemas.approval import SubmitApprovalDecisionRequest
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.human_approval_service import (
    APPROVALS_ARTIFACT_NAME,
    HUMAN_FEEDBACK_ARTIFACT_NAME,
    HumanApprovalService,
    RunNotAwaitingApprovalError,
)
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_approval_repository import InMemoryApprovalRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_peer_review_result_repository import InMemoryPeerReviewResultRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_self_correction_cycle_repository import InMemorySelfCorrectionCycleRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def human_approval_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    peer_review_result_repository = InMemoryPeerReviewResultRepository()
    self_correction_cycle_repository = InMemorySelfCorrectionCycleRepository()
    approval_repository = InMemoryApprovalRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = HumanApprovalService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        approval_repository=approval_repository,
        event_repository=event_repository,
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        approval_repository,
        event_repository,
    )


def _high_risk_patch_plan(run_id: str) -> PatchPlan:
    now = datetime.now(UTC)
    return PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=run_id,
        issue_group_id=str(ObjectId()),
        title="Auth security issue",
        root_cause="Unsafe auth handling",
        affected_files=["src/auth/login.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth/login.py",
                description="Harden auth flow",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest"],
        estimated_risk=RiskLevel.HIGH,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Security fix",
        rollback_strategy="Restore auth module",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def test_prepare_approvals_requires_awaiting_status(human_approval_stack) -> None:
    service, run_service, project_service, *_ = human_approval_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Approval Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RunNotAwaitingApprovalError):
        service.prepare_approvals(user_id, run.id)


def test_prepare_approvals_when_status_advanced_but_risk_requires_approval(
    human_approval_stack,
) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        _approval_repository,
        _event_repository,
    ) = human_approval_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Approval Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    run_repository.update_status(run.id, user_id, RunStatus.FIXING)

    patch_plan = _high_risk_patch_plan(run.id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)

    response = service.prepare_approvals(user_id, run.id)

    assert response.approval_count == 1
    assert response.pending_count == 1
    assert response.run_status == RunStatus.AWAITING_APPROVAL.value

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.AWAITING_APPROVAL


def test_should_resume_pipeline_after_risk_gate_approval(human_approval_stack) -> None:
    service, *_ = human_approval_stack
    assert service.should_resume_pipeline_after_decision(
        HumanDecision.APPROVE,
        ApprovalTrigger.RISK_GATE,
        RunStatus.FIXING,
    )
    assert not service.should_resume_pipeline_after_decision(
        HumanDecision.REJECT,
        ApprovalTrigger.RISK_GATE,
        RunStatus.FAILED,
    )


def test_has_blocking_risk_gate_approval(human_approval_stack) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        fix_plan_repository,
        risk_decision_repository,
        _approval_repository,
        _event_repository,
    ) = human_approval_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Approval Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    patch_plan = _high_risk_patch_plan(run.id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)

    assert service.has_blocking_risk_gate_approval(run.id)

    service.prepare_approvals(user_id, run.id)
    assert service.has_blocking_risk_gate_approval(run.id)

    prepared = service.prepare_approvals(user_id, run.id)
    approval_id = prepared.approvals[0].approval_id
    service.submit_decision(
        user_id,
        run.id,
        approval_id,
        SubmitApprovalDecisionRequest(decision=HumanDecision.APPROVE),
    )
    assert not service.has_blocking_risk_gate_approval(run.id)


def test_prepare_and_approve_risk_gate_approval(human_approval_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        approval_repository,
        event_repository,
    ) = human_approval_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Approval Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    run_repository.update_status(run.id, user_id, RunStatus.AWAITING_APPROVAL)

    patch_plan = _high_risk_patch_plan(run.id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)

    response = service.prepare_approvals(user_id, run.id)
    assert response.approval_count == 1
    assert response.pending_count == 1

    workspace = workspace_manager.get_run_workspace(run.id)
    assert (workspace.baseline / APPROVALS_ARTIFACT_NAME).is_file()

    approval_id = response.approvals[0].approval_id
    decision = service.submit_decision(
        user_id,
        run.id,
        approval_id,
        SubmitApprovalDecisionRequest(decision=HumanDecision.APPROVE),
    )

    assert decision.run_status == RunStatus.FIXING.value
    assert decision.approval.status == ApprovalStatus.APPROVED

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.FIXING

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "APPROVAL_REQUIRED" for event in events)
    assert any(event.event_type.value == "HUMAN_APPROVED" for event in events)


def test_request_changes_writes_feedback_and_moves_to_planning(human_approval_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        _approval_repository,
        _event_repository,
    ) = human_approval_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Approval Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    run_repository.update_status(run.id, user_id, RunStatus.AWAITING_APPROVAL)

    patch_plan = _high_risk_patch_plan(run.id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)

    prepared = service.prepare_approvals(user_id, run.id)
    approval_id = prepared.approvals[0].approval_id
    decision = service.submit_decision(
        user_id,
        run.id,
        approval_id,
        SubmitApprovalDecisionRequest(
            decision=HumanDecision.REQUEST_CHANGES,
            feedback="Add stronger auth validation before retrying",
        ),
    )

    assert decision.run_status == RunStatus.PLANNING.value
    assert decision.replanning_required is True

    workspace = workspace_manager.get_run_workspace(run.id)
    feedback_path = workspace.baseline / HUMAN_FEEDBACK_ARTIFACT_NAME
    assert feedback_path.is_file()
    assert "stronger auth validation" in feedback_path.read_text(encoding="utf-8")
