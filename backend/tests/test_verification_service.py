from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.scanners.runner import CallableCommandRunner, ProcessResult
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.code_fix_service import FIX_ATTEMPTS_ARTIFACT_NAME
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.verification_service import (
    VERIFICATION_RESULTS_ARTIFACT_NAME,
    FixAttemptsRequiredError,
    VerificationService,
)
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


def _verification_runner() -> CallableCommandRunner:
    def handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        executable = command[0]
        if command[-1] == "--version":
            return ProcessResult(command, cwd, 0, f"{executable} 1.0.0", "", now, now)
        if executable == "bash":
            return ProcessResult(command, cwd, 0, "", "", now, now)
        if executable == "ruff":
            return ProcessResult(command, cwd, 0, "[]", "", now, now)
        if executable == "pytest":
            return ProcessResult(command, cwd, 0, "1 passed", "", now, now)
        return ProcessResult(command, cwd, 0, "", "", now, now)

    return CallableCommandRunner(handler)


@pytest.fixture
def verification_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = VerificationService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        event_repository=event_repository,
        command_runner=_verification_runner(),
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        fix_attempt_repository,
        verification_result_repository,
        event_repository,
    )


def _lint_patch_plan(run_id: str, patch_plan_id: str, fix_attempt_id: str) -> PatchPlan:
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


def _applied_fix_attempt(run_id: str, patch_plan_id: str, fix_attempt_id: str) -> FixAttempt:
    return FixAttempt(
        fix_attempt_id=fix_attempt_id,
        run_id=run_id,
        patch_plan_id=patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/utils.py"],
        changed_files=["src/utils.py"],
        created_at=datetime.now(UTC),
    )


def _seed_working_copy(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    target = workspace.working / "src" / "utils.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("fixed_var = 1\n", encoding="utf-8")


def test_verify_run_passes_applied_fix(
    verification_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        fix_attempt_repository,
        verification_result_repository,
        event_repository,
    ) = verification_stack
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Verify Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_copy(workspace_manager, run.id)

    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    patch_plan = _lint_patch_plan(run.id, patch_plan_id, fix_attempt_id)
    fix_attempt = _applied_fix_attempt(run.id, patch_plan_id, fix_attempt_id)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    fix_attempt_repository.add(fix_attempt)

    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / FIX_ATTEMPTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.verify_run(user_id, run.id)

    assert response.passed_count == 1
    assert response.failed_count == 0
    assert response.run_status == RunStatus.VERIFYING.value
    assert (workspace.baseline / VERIFICATION_RESULTS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.VERIFYING

    results = verification_result_repository.list_by_run(run.id)
    assert results[0].status == VerificationStatus.PASSED

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "VERIFICATION_STARTED" for event in events)
    assert any(event.event_type.value == "VERIFICATION_PASSED" for event in events)


def test_verify_run_requires_fix_attempts(verification_stack) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _fix_plan_repository,
        _fix_attempt_repository,
        _verification_result_repository,
        _event_repository,
    ) = verification_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="No Attempts"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(FixAttemptsRequiredError):
        service.verify_run(user_id, run.id)


def test_verify_run_moves_to_self_correcting_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)

    def failing_handler(command: list[str], cwd: str, timeout_seconds: int) -> ProcessResult:
        del timeout_seconds
        now = datetime.now(UTC)
        if command[0] == "bash":
            return ProcessResult(command, cwd, 1, "", "failed", now, now)
        if command[-1] == "--version":
            return ProcessResult(command, cwd, 0, "tool 1.0.0", "", now, now)
        return ProcessResult(command, cwd, 0, "[]", "", now, now)

    service = VerificationService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        event_repository=event_repository,
        command_runner=CallableCommandRunner(failing_handler),
    )

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Fail Verify"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_copy(workspace_manager, run.id)

    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    fix_plan_repository.replace_for_run(
        run.id,
        [_lint_patch_plan(run.id, patch_plan_id, fix_attempt_id)],
    )
    fix_attempt_repository.add(_applied_fix_attempt(run.id, patch_plan_id, fix_attempt_id))

    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / FIX_ATTEMPTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.verify_run(user_id, run.id)

    assert response.failed_count == 1
    assert response.run_status == RunStatus.SELF_CORRECTING.value
    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.SELF_CORRECTING

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "VERIFICATION_FAILED" for event in events)
