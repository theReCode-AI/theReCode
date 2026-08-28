from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.adk.git_finalization.engine import GitFinalizationContext, GitFinalizationEngine
from app.git.local import LocalGitClient
from app.git.types import (
    BranchResult,
    CommitResult,
    GitOperationResult,
    PullRequestResult,
    PushResult,
)
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.git_operation_enums import GitOperationStatus
from app.models.patch_plan import ExpectedModification, PatchPlan
from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
from app.workspace import WorkspaceManager


@pytest.fixture
def git_finalization_context(tmp_path: Path):
    run_id = str(ObjectId())
    workspace_manager = WorkspaceManager(tmp_path)
    workspace = workspace_manager.create_run_workspace(run_id)
    git_dir = workspace.repository / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    target = workspace.working / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan = PatchPlan(
        patch_plan_id=str(ObjectId()),
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
        expected_tests=["uv run pytest"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval with safe parser",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    fix_attempt = FixAttempt(
        fix_attempt_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan.patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/auth.py"],
        changed_files=["src/auth.py"],
        created_at=now,
    )
    context = GitFinalizationContext(
        run_id=run_id,
        workspace=workspace,
        repository_full_name="org/repo",
        default_branch="main",
        patch_plans=[patch_plan],
        fix_attempts=[fix_attempt],
        verification_results=[],
        peer_reviews=[],
        self_correction_cycles=[],
        changed_files=["src/auth.py"],
    )
    return context


def test_finalize_creates_branch_commit_push_and_pr(git_finalization_context) -> None:
    local_git = MagicMock(spec=LocalGitClient)
    local_git.get_current_branch.return_value = "main"
    local_git.create_branch.return_value = BranchResult(success=True, branch_name="agent/run")
    local_git.stage_files.return_value = GitOperationResult(success=True)
    local_git.commit.return_value = CommitResult(success=True, commit_sha="abc123")
    local_git.push.return_value = PushResult(success=True, commit_sha="abc123")

    provider = MagicMock()
    provider.authenticated_remote_url.return_value = "https://example.com/org/repo.git"
    provider.create_pull_request.return_value = PullRequestResult(
        success=True,
        url="https://github.com/org/repo/pull/1",
        number=1,
    )

    result = GitFinalizationEngine(local_git=local_git).finalize(
        git_finalization_context,
        provider,
        "token",
    )

    assert result.status == GitOperationStatus.PR_CREATED
    assert result.pull_request_url == "https://github.com/org/repo/pull/1"
    assert result.branch_name is not None
    provider.create_pull_request.assert_called_once()
