from datetime import UTC, datetime
from pathlib import Path

import pytest
from bson import ObjectId

from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.regression_test_enums import RegressionTestStatus
from app.models.regression_test_result import RegressionTestResult
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.peer_review_service import (
    PEER_REVIEW_RESULTS_ARTIFACT_NAME,
    PeerReviewService,
    RegressionTestsRequiredError,
)
from app.services.project_service import ProjectService
from app.services.regression_test_service import REGRESSION_TEST_RESULTS_ARTIFACT_NAME
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_peer_review_result_repository import InMemoryPeerReviewResultRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_regression_test_result_repository import InMemoryRegressionTestResultRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def peer_review_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    regression_test_result_repository = InMemoryRegressionTestResultRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    peer_review_result_repository = InMemoryPeerReviewResultRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = PeerReviewService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        regression_test_result_repository=regression_test_result_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        event_repository=event_repository,
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        fix_attempt_repository,
        regression_test_result_repository,
        verification_result_repository,
        peer_review_result_repository,
        event_repository,
    )


def _seed_review_inputs(
    workspace_manager: WorkspaceManager,
    run_id: str,
    diff_text: str = (
        "--- a/src/auth.py\n+++ b/src/auth.py\n@@\n-TOKEN = eval('1')\n+TOKEN = 'safe'\n"
    ),
) -> tuple[PatchPlan, FixAttempt, VerificationResult, RegressionTestResult]:
    workspace = workspace_manager.get_run_workspace(run_id)
    target = workspace.working / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")

    diff_path = workspace.patches / "plan" / "changes.diff"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff_text, encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    verification_result_id = str(ObjectId())
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
                change_type=ChangeType.SECURITY_REMEDIATION.value,
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
    fix_attempt = FixAttempt(
        fix_attempt_id=fix_attempt_id,
        run_id=run_id,
        patch_plan_id=patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/auth.py"],
        changed_files=["src/auth.py"],
        diff_artifact_path=str(diff_path),
        created_at=now,
    )
    verification = VerificationResult(
        verification_result_id=verification_result_id,
        run_id=run_id,
        fix_attempt_id=fix_attempt_id,
        patch_plan_id=patch_plan_id,
        status=VerificationStatus.PASSED,
        created_at=now,
    )
    regression = RegressionTestResult(
        regression_test_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan_id,
        fix_attempt_id=fix_attempt_id,
        verification_result_id=verification_result_id,
        status=RegressionTestStatus.PASSED,
        eligible=True,
        test_file_path="tests/regression/test_regression_example.py",
        targeted_passed=1,
        suite_passed=1,
        created_at=now,
    )
    return patch_plan, fix_attempt, verification, regression


def test_review_run_requires_regression_results(peer_review_stack) -> None:
    service, run_service, project_service, *_ = peer_review_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Peer Review Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RegressionTestsRequiredError):
        service.review_run(user_id, run.id)


def test_review_run_approves_clean_fix(peer_review_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        fix_attempt_repository,
        regression_test_result_repository,
        verification_result_repository,
        peer_review_result_repository,
        event_repository,
    ) = peer_review_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Peer Review Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    patch_plan, fix_attempt, verification, regression = _seed_review_inputs(
        workspace_manager,
        run.id,
    )
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    fix_attempt_repository.add(fix_attempt)
    verification_result_repository.add(verification)
    regression_test_result_repository.add(regression)

    workspace = workspace_manager.get_run_workspace(run.id)
    workspace.baseline.mkdir(parents=True, exist_ok=True)
    (workspace.baseline / REGRESSION_TEST_RESULTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    response = service.review_run(user_id, run.id)

    assert response.result_count == 1
    assert response.approved_count == 1
    assert response.run_status == RunStatus.FINAL_REVIEW.value
    assert (workspace.baseline / PEER_REVIEW_RESULTS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.FINAL_REVIEW

    results = peer_review_result_repository.list_by_run(run.id)
    assert results[0].verdict == PeerReviewVerdict.APPROVED
    assert len(results[0].reviewer_opinions) == 3

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "PEER_REVIEW_STARTED" for event in events)
    assert any(event.event_type.value == "PEER_REVIEW_APPROVED" for event in events)

    detail = service.get_peer_review(user_id, run.id, results[0].peer_review_id)
    assert detail.peer_review_id == results[0].peer_review_id
