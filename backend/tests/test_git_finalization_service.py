from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.adk.git_finalization.engine import GitFinalizationResult
from app.core.config import Settings
from app.git.providers import GitProviderFactory
from app.git.types import RepositoryValidationResult
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.git_operation_enums import GitOperationStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.peer_review_result import PeerReviewResult
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.schemas.git import GitCredentialCreate
from app.schemas.project import ProjectCreate, RepositoryCreate
from app.schemas.run import RunCreate
from app.services.git_credential_service import GitCredentialService
from app.services.git_finalization_service import (
    GIT_OPERATIONS_ARTIFACT_NAME,
    GitFinalizationService,
    RunNotReadyForGitFinalizationError,
)
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_approval_repository import InMemoryApprovalRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_git_operation_repository import InMemoryGitOperationRepository
from tests.test_git_service import InMemoryGitCredentialRepository
from tests.test_peer_review_result_repository import InMemoryPeerReviewResultRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_self_correction_cycle_repository import InMemorySelfCorrectionCycleRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        credentials_encryption_key="phase5-test-encryption-key-value",
    )


@pytest.fixture
def git_finalization_stack(tmp_path: Path, settings):
    run_repository = InMemoryRunRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    peer_review_result_repository = InMemoryPeerReviewResultRepository()
    self_correction_cycle_repository = InMemorySelfCorrectionCycleRepository()
    approval_repository = InMemoryApprovalRepository()
    git_operation_repository = InMemoryGitOperationRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    git_credential_service = GitCredentialService(
        InMemoryGitCredentialRepository(),
        settings,
    )
    provider_factory = MagicMock(spec=GitProviderFactory)
    finalization_agent = MagicMock()
    service = GitFinalizationService(
        run_repository=run_repository,
        run_service=run_service,
        project_service=project_service,
        git_credential_service=git_credential_service,
        provider_factory=provider_factory,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        approval_repository=approval_repository,
        git_operation_repository=git_operation_repository,
        event_repository=event_repository,
        finalization_agent=finalization_agent,
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
        peer_review_result_repository,
        git_operation_repository,
        event_repository,
        provider_factory,
        finalization_agent,
        git_credential_service,
    )


def _seed_success_inputs(
    workspace_manager: WorkspaceManager,
    run_id: str,
    patch_plan_id: str,
    fix_attempt_id: str,
    verification_result_id: str,
) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    git_dir = workspace.repository / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    target = workspace.working / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")


def test_finalize_run_requires_final_review_status(git_finalization_stack) -> None:
    service, run_service, project_service, *_ = git_finalization_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Git Finalize"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RunNotReadyForGitFinalizationError):
        service.finalize_run(user_id, run.id)


def test_finalize_run_persists_pr_operation(git_finalization_stack, settings) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        fix_plan_repository,
        fix_attempt_repository,
        verification_result_repository,
        peer_review_result_repository,
        git_operation_repository,
        event_repository,
        provider_factory,
        finalization_agent,
        git_credential_service,
    ) = git_finalization_stack

    user_id = str(ObjectId())
    git_credential_service.save_credential(
        user_id,
        GitCredentialCreate(provider="github", access_token="ghp_secret"),
    )
    project = project_service.create_project(user_id, ProjectCreate(name="Git Finalize"))
    repository = project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="github", full_name="org/repo"),
    )
    run = run_service.create_run(
        user_id,
        RunCreate(project_id=project.id, repository_id=repository.id),
    )
    run_repository.update_status(run.id, user_id, RunStatus.FINAL_REVIEW)

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    verification_result_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run.id,
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
        expected_tests=["uv run pytest"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    fix_plan_repository.replace_for_run(run.id, [patch_plan])
    fix_attempt_repository.add(
        FixAttempt(
            fix_attempt_id=fix_attempt_id,
            run_id=run.id,
            patch_plan_id=patch_plan_id,
            attempt_number=1,
            status=FixAttemptStatus.APPLIED,
            planned_files=["src/auth.py"],
            changed_files=["src/auth.py"],
            created_at=now,
        ),
    )
    verification_result_repository.add(
        VerificationResult(
            verification_result_id=verification_result_id,
            run_id=run.id,
            fix_attempt_id=fix_attempt_id,
            patch_plan_id=patch_plan_id,
            status=VerificationStatus.PASSED,
            created_at=now,
        ),
    )
    peer_review_result_repository.add(
        PeerReviewResult(
            peer_review_id=str(ObjectId()),
            run_id=run.id,
            patch_plan_id=patch_plan_id,
            fix_attempt_id=fix_attempt_id,
            verification_result_id=verification_result_id,
            regression_test_id=str(ObjectId()),
            verdict=PeerReviewVerdict.APPROVED,
            synthesis_summary="Approved",
            reviewer_opinions=[],
            created_at=now,
        ),
    )
    _seed_success_inputs(
        workspace_manager,
        run.id,
        patch_plan_id,
        fix_attempt_id,
        verification_result_id,
    )

    mock_provider = MagicMock()
    mock_provider.validate_repository.return_value = RepositoryValidationResult(
        valid=True,
        provider="github",
        full_name="org/repo",
        default_branch="main",
        clone_url="https://github.com/org/repo.git",
    )
    provider_factory.get_provider.return_value = mock_provider
    finalization_agent.finalize.return_value = GitFinalizationResult(
        status=GitOperationStatus.PR_CREATED,
        branch_name="agent/run-security",
        base_branch="main",
        commit_sha="abc123",
        push_commit_sha="abc123",
        pull_request_url="https://github.com/org/repo/pull/1",
        pull_request_number=1,
        title="theReCode: Security issue",
        description="PR body",
    )

    response = service.finalize_run(user_id, run.id)

    assert response.operation.status == GitOperationStatus.PR_CREATED
    assert response.run_status == RunStatus.REPORTING.value
    assert len(git_operation_repository.list_by_run(run.id)) == 1
    workspace = workspace_manager.get_run_workspace(run.id)
    assert (workspace.baseline / GIT_OPERATIONS_ARTIFACT_NAME).is_file()

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "GIT_PR_CREATED" for event in events)
