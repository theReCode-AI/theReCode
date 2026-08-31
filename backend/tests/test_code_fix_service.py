from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.adk.agents.code_fix_agent import CodeFixAgent
from app.adk.risk.policy_engine import RiskPolicyEngine
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.code_fix_service import (
    FIX_ATTEMPTS_ARTIFACT_NAME,
    CodeFixService,
    RiskDecisionsRequiredError,
)
from app.services.project_service import ProjectService
from app.services.risk_assessment_service import RISK_DECISIONS_ARTIFACT_NAME
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_fix_command_runner
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_approval_repository import InMemoryApprovalRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository


def _lint_patch_plan(run_id: str, file_path: str = "src/utils.py") -> PatchPlan:
    now = datetime.now(UTC)
    return PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=run_id,
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused variable",
        affected_files=[file_path],
        expected_modifications=[
            ExpectedModification(
                file=file_path,
                description="Remove unused variable",
                change_type=ChangeType.LINT_FIX.value,
            ),
        ],
        expected_tests=["uv run ruff check src/utils.py"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )


def _build_fix_command_runner(extra_file: str | None = None):
    return build_fix_command_runner(extra_file)


@pytest.fixture
def code_fix_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = CodeFixService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        approval_repository=InMemoryApprovalRepository(),
        event_repository=event_repository,
        code_fix_agent=CodeFixAgent(),
        command_runner=_build_fix_command_runner(),
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        fix_attempt_repository,
        event_repository,
    )


def _seed_working_repo(
    workspace_manager: WorkspaceManager,
    run_id: str,
    file_path: str = "src/utils.py",
) -> Path:
    workspace = workspace_manager.get_run_workspace(run_id)
    target = workspace.repository / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unused_var = 1\n", encoding="utf-8")
    return target


def test_fix_run_applies_autonomous_plan(code_fix_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        fix_attempt_repository,
        event_repository,
    ) = code_fix_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Fix Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_repo(workspace_manager, run.id)

    patch_plan = _lint_patch_plan(run.id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)
    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / RISK_DECISIONS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.fix_run(user_id, run.id)

    assert response.applied_count == 1
    assert response.skipped_count == 0
    assert response.run_status == RunStatus.FIXING.value
    assert (workspace.working / "src" / "utils.py").read_text(encoding="utf-8") == "fixed_var = 1\n"
    assert (workspace.baseline / FIX_ATTEMPTS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.FIXING

    attempts = fix_attempt_repository.list_by_run(run.id)
    assert attempts[0].status == FixAttemptStatus.APPLIED
    assert attempts[0].changed_files == ["src/utils.py"]

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "PATCH_APPLIED" for event in events)


def test_fix_run_skips_non_autonomous_plan(code_fix_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        _run_repository,
        fix_plan_repository,
        risk_decision_repository,
        fix_attempt_repository,
        _event_repository,
    ) = code_fix_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Skip Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_repo(workspace_manager, run.id)

    patch_plan = _lint_patch_plan(run.id, file_path="src/auth/login.py")
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)
    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / RISK_DECISIONS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.fix_run(user_id, run.id)

    assert response.applied_count == 0
    assert response.skipped_count == 1
    assert response.run_status == RunStatus.COMPLETED.value
    attempts = fix_attempt_repository.list_by_run(run.id)
    assert attempts[0].status == FixAttemptStatus.SKIPPED
    stored_run = _run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.COMPLETED


def test_fix_run_rolls_back_scope_violation(tmp_path: Path) -> None:
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = CodeFixService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        event_repository=event_repository,
        code_fix_agent=CodeFixAgent(),
        command_runner=_build_fix_command_runner(extra_file="src/unexpected.py"),
    )

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Rollback Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_repo(workspace_manager, run.id)

    patch_plan = _lint_patch_plan(run.id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)
    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / RISK_DECISIONS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.fix_run(user_id, run.id)

    assert response.rolled_back_count == 1
    working_file = workspace.working / "src" / "utils.py"
    assert working_file.read_text(encoding="utf-8") == "unused_var = 1\n"
    assert not (workspace.working / "src" / "unexpected.py").exists()
    attempts = fix_attempt_repository.list_by_run(run.id)
    assert attempts[0].status == FixAttemptStatus.ROLLED_BACK
    assert attempts[0].scope_violation is True


def test_fix_run_requires_risk_decisions(code_fix_stack) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _fix_plan_repository,
        _risk_decision_repository,
        _fix_attempt_repository,
        _event_repository,
    ) = code_fix_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="No Risk"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RiskDecisionsRequiredError):
        service.fix_run(user_id, run.id)


def test_fix_run_applies_after_risk_gate_approval(code_fix_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        _run_repository,
        fix_plan_repository,
        risk_decision_repository,
        fix_attempt_repository,
        _event_repository,
    ) = code_fix_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Approved Fix"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_repo(workspace_manager, run.id, file_path="src/auth/login.py")

    patch_plan = _lint_patch_plan(run.id, file_path="src/auth/login.py")
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)
    assert risk_decisions[0].autonomous_fix_allowed is False

    approval_repository = service._approval_repository
    assert approval_repository is not None
    from datetime import UTC, datetime

    from app.models.approval import HumanApproval
    from app.models.approval_enums import ApprovalStatus, ApprovalTrigger

    approval_repository.add(
        HumanApproval(
            approval_id=str(ObjectId()),
            run_id=run.id,
            patch_plan_id=patch_plan.patch_plan_id,
            trigger=ApprovalTrigger.RISK_GATE,
            status=ApprovalStatus.APPROVED,
            reason="Approved for autonomous fix",
            created_at=datetime.now(UTC),
        ),
    )

    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / RISK_DECISIONS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.fix_run(user_id, run.id)

    assert response.applied_count == 1
    assert response.skipped_count == 0
    attempts = fix_attempt_repository.list_by_run(run.id)
    assert attempts[0].status == FixAttemptStatus.APPLIED
    assert attempts[0].changed_files == ["src/auth/login.py"]
