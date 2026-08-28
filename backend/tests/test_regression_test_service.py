from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.regression_test_enums import RegressionTestStatus
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.project_service import ProjectService
from app.services.regression_test_service import (
    REGRESSION_TEST_RESULTS_ARTIFACT_NAME,
    PassedVerificationsRequiredError,
    RegressionTestService,
)
from app.services.run_service import RunService
from app.services.verification_service import VERIFICATION_RESULTS_ARTIFACT_NAME
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_mock_command_runner
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_regression_test_result_repository import InMemoryRegressionTestResultRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def regression_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    regression_test_result_repository = InMemoryRegressionTestResultRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = RegressionTestService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        verification_result_repository=verification_result_repository,
        regression_test_result_repository=regression_test_result_repository,
        event_repository=event_repository,
        command_runner=build_mock_command_runner(),
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        verification_result_repository,
        regression_test_result_repository,
        event_repository,
    )


def _patch_plan(run_id: str, change_type: ChangeType) -> tuple[PatchPlan, str, str]:
    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run_id,
        issue_group_id=str(ObjectId()),
        title="Security issue",
        root_cause="Unsafe eval usage",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Remove eval",
                change_type=change_type.value,
            ),
        ],
        expected_tests=["uv run pytest tests/test_auth.py"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval with safe parser",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    return patch_plan, fix_attempt_id, patch_plan_id


def _passed_verification(
    run_id: str,
    patch_plan_id: str,
    fix_attempt_id: str,
) -> VerificationResult:
    return VerificationResult(
        verification_result_id=str(ObjectId()),
        run_id=run_id,
        fix_attempt_id=fix_attempt_id,
        patch_plan_id=patch_plan_id,
        status=VerificationStatus.PASSED,
        created_at=datetime.now(UTC),
    )


def _seed_working_copy(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    target = workspace.working / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")


def test_run_regression_tests_requires_passed_verifications(regression_stack) -> None:
    service, run_service, project_service, *_ = regression_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Regression Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(PassedVerificationsRequiredError):
        service.run_regression_tests(user_id, run.id)


def test_run_regression_tests_skips_lint_only_verified_fix(regression_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        verification_result_repository,
        regression_test_result_repository,
        event_repository,
    ) = regression_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Regression Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_copy(workspace_manager, run.id)

    patch_plan, fix_attempt_id, patch_plan_id = _patch_plan(run.id, ChangeType.LINT_FIX)
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    verification_result_repository.add(
        _passed_verification(run.id, patch_plan_id, fix_attempt_id),
    )

    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / VERIFICATION_RESULTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.run_regression_tests(user_id, run.id)

    assert response.result_count == 1
    assert response.skipped_count == 1
    assert response.passed_count == 0
    assert response.run_status == RunStatus.VERIFYING.value
    assert (workspace.baseline / REGRESSION_TEST_RESULTS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.VERIFYING

    results = regression_test_result_repository.list_by_run(run.id)
    assert results[0].status == RegressionTestStatus.SKIPPED

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "REGRESSION_TEST_STARTED" for event in events)


def test_run_regression_tests_passes_meaningful_fix(regression_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        verification_result_repository,
        regression_test_result_repository,
        event_repository,
    ) = regression_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Regression Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_working_copy(workspace_manager, run.id)

    patch_plan, fix_attempt_id, patch_plan_id = _patch_plan(
        run.id,
        ChangeType.SECURITY_REMEDIATION,
    )
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    verification_result_repository.add(
        _passed_verification(run.id, patch_plan_id, fix_attempt_id),
    )

    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / VERIFICATION_RESULTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.run_regression_tests(user_id, run.id)

    assert response.result_count == 1
    assert response.passed_count == 1
    assert response.failed_count == 0
    assert response.run_status == RunStatus.VERIFYING.value

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.VERIFYING

    results = regression_test_result_repository.list_by_run(run.id)
    assert results[0].status == RegressionTestStatus.PASSED
    assert results[0].test_file_path is not None

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "REGRESSION_TEST_PASSED" for event in events)

    detail = service.get_regression_test(user_id, run.id, results[0].regression_test_id)
    assert detail.regression_test_id == results[0].regression_test_id
