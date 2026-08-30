from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.run import RunStatus
from app.models.self_correction_enums import SelfCorrectionStatus
from app.models.verification_enums import (
    VerificationCheckStatus,
    VerificationCheckType,
    VerificationStatus,
)
from app.models.verification_result import VerificationCheck, VerificationResult
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.self_correction_service import (
    SELF_CORRECTION_CYCLES_ARTIFACT_NAME,
    SelfCorrectionService,
    VerificationFailuresRequiredError,
)
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_fix_command_runner
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_self_correction_cycle_repository import InMemorySelfCorrectionCycleRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def self_correction_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    self_correction_cycle_repository = InMemorySelfCorrectionCycleRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = SelfCorrectionService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        event_repository=event_repository,
        command_runner=build_fix_command_runner(),
        max_fix_iterations=3,
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
        verification_result_repository,
        self_correction_cycle_repository,
        event_repository,
    )


def _lint_patch_plan(run_id: str, patch_plan_id: str) -> PatchPlan:
    now = datetime.now(UTC)
    return PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run_id,
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused variable",
        affected_files=["src/utils.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/utils.py",
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


def _seed_working_copy(workspace_manager: WorkspaceManager, run_id: str) -> Path:
    workspace = workspace_manager.get_run_workspace(run_id)
    backup_root = workspace.patches / "plan" / "pre-patch"
    backup_root.mkdir(parents=True, exist_ok=True)
    target = workspace.working / "src" / "utils.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unused_var = 1\n", encoding="utf-8")
    backup_target = backup_root / "src" / "utils.py"
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    backup_target.write_text("unused_var = 1\n", encoding="utf-8")
    return target


def test_correct_run_retries_failed_verification(
    self_correction_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.adk.risk.policy_engine import RiskPolicyEngine

    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        risk_decision_repository,
        fix_attempt_repository,
        verification_result_repository,
        self_correction_cycle_repository,
        event_repository,
    ) = self_correction_stack
    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Correct Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_copy(workspace_manager, run.id)

    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    patch_plan = _lint_patch_plan(run.id, patch_plan_id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(run.id, risk_decisions)

    workspace = workspace_manager.get_run_workspace(run.id)
    backup_path = workspace.patches / patch_plan_id / "pre-patch"
    backup_path.mkdir(parents=True, exist_ok=True)
    backup_file = backup_path / "src" / "utils.py"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text("unused_var = 1\n", encoding="utf-8")

    fix_attempt_repository.add(
        FixAttempt(
            fix_attempt_id=fix_attempt_id,
            run_id=run.id,
            patch_plan_id=patch_plan_id,
            attempt_number=1,
            status=FixAttemptStatus.APPLIED,
            planned_files=["src/utils.py"],
            changed_files=["src/utils.py"],
            backup_path=str(backup_path),
            created_at=datetime.now(UTC),
        ),
    )
    verification_result_repository.add(
        VerificationResult(
            verification_result_id=str(ObjectId()),
            run_id=run.id,
            fix_attempt_id=fix_attempt_id,
            patch_plan_id=patch_plan_id,
            status=VerificationStatus.FAILED,
            checks=[
                VerificationCheck(
                    check_type=VerificationCheckType.COMMAND,
                    name="uv run ruff check src/utils.py",
                    status=VerificationCheckStatus.FAILED,
                    exit_code=1,
                    message="lint still failing",
                ),
            ],
            passed_checks=0,
            failed_checks=1,
            failure_summary="lint still failing",
            created_at=datetime.now(UTC),
        ),
    )

    response = service.correct_run(user_id, run.id)

    assert response.passed_count == 1
    assert response.run_status == RunStatus.VERIFYING.value
    assert (workspace.baseline / SELF_CORRECTION_CYCLES_ARTIFACT_NAME).is_file()

    cycles = self_correction_cycle_repository.list_by_run(run.id)
    assert cycles[0].status == SelfCorrectionStatus.PASSED
    assert cycles[0].rollback_applied is True
    assert fix_attempt_repository.count_by_patch_plan(run.id, patch_plan_id) == 2

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "SELF_CORRECTION_STARTED" for event in events)
    assert any(event.event_type.value == "SELF_CORRECTION_COMPLETED" for event in events)


def test_correct_run_requires_failed_verification(self_correction_stack) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _fix_plan_repository,
        _risk_decision_repository,
        _fix_attempt_repository,
        _verification_result_repository,
        _self_correction_cycle_repository,
        _event_repository,
    ) = self_correction_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="No Failures"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(VerificationFailuresRequiredError):
        service.correct_run(user_id, run.id)


def test_correct_run_exhausts_iterations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.adk.risk.policy_engine import RiskPolicyEngine

    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    self_correction_cycle_repository = InMemorySelfCorrectionCycleRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = SelfCorrectionService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        event_repository=event_repository,
        command_runner=build_fix_command_runner(),
        max_fix_iterations=3,
    )

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Exhausted"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    patch_plan_id = str(ObjectId())
    patch_plan = _lint_patch_plan(run.id, patch_plan_id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    risk_decision_repository.replace_for_run(
        run.id,
        RiskPolicyEngine().assess(run.id, [patch_plan]),
    )

    now = datetime.now(UTC)
    for attempt_number in range(1, 4):
        fix_attempt_repository.add(
            FixAttempt(
                fix_attempt_id=str(ObjectId()),
                run_id=run.id,
                patch_plan_id=patch_plan_id,
                attempt_number=attempt_number,
                status=FixAttemptStatus.APPLIED,
                planned_files=["src/utils.py"],
                created_at=now,
            ),
        )

    latest_fix_attempt_id = fix_attempt_repository.list_by_run(run.id)[-1].fix_attempt_id
    verification_result_repository.add(
        VerificationResult(
            verification_result_id=str(ObjectId()),
            run_id=run.id,
            fix_attempt_id=latest_fix_attempt_id,
            patch_plan_id=patch_plan_id,
            status=VerificationStatus.FAILED,
            checks=[],
            passed_checks=0,
            failed_checks=1,
            failure_summary="still failing",
            created_at=now,
        ),
    )

    response = service.correct_run(user_id, run.id)

    assert response.exhausted_count == 1
    assert response.run_status == RunStatus.AWAITING_APPROVAL.value
