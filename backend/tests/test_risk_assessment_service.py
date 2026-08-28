from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.risk_enums import AutonomyDecision
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.fix_planner_service import FIX_PLANS_ARTIFACT_NAME
from app.services.project_service import ProjectService
from app.services.risk_assessment_service import (
    RISK_DECISIONS_ARTIFACT_NAME,
    PatchPlansRequiredError,
    RiskAssessmentService,
)
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository


@pytest.fixture
def risk_assessment_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = RiskAssessmentService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
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
        event_repository,
    )


def test_assess_run_persists_risk_decisions(risk_assessment_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        event_repository,
    ) = risk_assessment_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Risk Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    now = datetime.now(UTC)
    patch_plan = PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=run.id,
        issue_group_id=str(ObjectId()),
        title="Secret issue",
        root_cause="Hardcoded secret",
        affected_files=["config/settings.py"],
        expected_modifications=[
            ExpectedModification(
                file="config/settings.py",
                description="Remove secret",
                change_type=ChangeType.SECRET_REMOVAL.value,
            ),
        ],
        expected_tests=["uv run gitleaks detect --source ."],
        estimated_risk=RiskLevel.CRITICAL,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Rotate secret",
        rollback_strategy="Restore file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / FIX_PLANS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.assess_run(user_id, run.id)

    assert response.decision_count == 1
    assert response.approval_required_count == 1
    assert response.autonomous_count == 0
    assert response.run_status == RunStatus.AWAITING_APPROVAL.value

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.AWAITING_APPROVAL

    decisions = risk_decision_repository.list_by_run(run.id)
    assert decisions[0].autonomy_decision == AutonomyDecision.REQUIRES_APPROVAL
    assert (workspace.baseline / RISK_DECISIONS_ARTIFACT_NAME).is_file()

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "RISK_ASSESSED" for event in events)
    assert any(event.event_type.value == "APPROVAL_REQUIRED" for event in events)


def test_assess_run_requires_patch_plans(risk_assessment_stack) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _fix_plan_repository,
        _risk_decision_repository,
        _event_repository,
    ) = risk_assessment_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="No Plans"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(PatchPlansRequiredError):
        service.assess_run(user_id, run.id)
