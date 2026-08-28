"""Execute branch, commit, push, and pull-request creation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.adk.git_finalization.pr_description_builder import (
    PullRequestDescriptionContext,
    build_branch_name,
    build_pull_request_description,
    build_pull_request_title,
)
from app.git.local import LocalGitClient
from app.git.providers import GitProviderClient
from app.models.fix_attempt import FixAttempt
from app.models.git_operation_enums import GitOperationStatus
from app.models.patch_plan import PatchPlan
from app.models.peer_review_result import PeerReviewResult
from app.models.self_correction_cycle import SelfCorrectionCycle
from app.models.verification_result import VerificationResult
from app.workspace.models import RunWorkspace


@dataclass(frozen=True)
class GitFinalizationContext:
    run_id: str
    workspace: RunWorkspace
    repository_full_name: str
    default_branch: str
    patch_plans: list[PatchPlan]
    fix_attempts: list[FixAttempt]
    verification_results: list[VerificationResult]
    peer_reviews: list[PeerReviewResult]
    self_correction_cycles: list[SelfCorrectionCycle]
    changed_files: list[str]


@dataclass(frozen=True)
class GitFinalizationResult:
    status: GitOperationStatus
    branch_name: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    push_commit_sha: str | None = None
    pull_request_url: str | None = None
    pull_request_number: int | None = None
    title: str | None = None
    description: str | None = None
    failure_summary: str | None = None


class GitFinalizationEngine:
    """Create an agent branch, commit fixes, push, and open a PR/MR."""

    def __init__(
        self,
        local_git: LocalGitClient | None = None,
    ) -> None:
        self._local_git = local_git or LocalGitClient()

    def finalize(
        self,
        context: GitFinalizationContext,
        provider: GitProviderClient,
        access_token: str,
    ) -> GitFinalizationResult:
        git_root = self._prepare_git_root(context.workspace, context.changed_files)
        if git_root is None:
            return GitFinalizationResult(
                status=GitOperationStatus.FAILED,
                failure_summary="Repository is not initialized for git operations",
            )

        branch_name = build_branch_name(context.run_id, context.patch_plans)
        base_branch = (
            self._local_git.get_current_branch(git_root) or context.default_branch
        )
        if base_branch == branch_name:
            base_branch = context.default_branch

        branch_result = self._local_git.create_branch(git_root, branch_name)
        if not branch_result.success:
            return GitFinalizationResult(
                status=GitOperationStatus.FAILED,
                branch_name=branch_name,
                base_branch=base_branch,
                failure_summary=branch_result.message,
            )

        stage_result = self._local_git.stage_files(git_root, context.changed_files)
        if not stage_result.success:
            return GitFinalizationResult(
                status=GitOperationStatus.FAILED,
                branch_name=branch_name,
                base_branch=base_branch,
                failure_summary=stage_result.message,
            )

        title = build_pull_request_title(context.patch_plans, context.run_id)
        commit_message = f"{title}\n\nAutomated remediation by CodeThera."
        commit_result = self._local_git.commit(git_root, commit_message)
        if not commit_result.success:
            return GitFinalizationResult(
                status=GitOperationStatus.FAILED,
                branch_name=branch_name,
                base_branch=base_branch,
                failure_summary=commit_result.message,
            )

        authenticated_url = provider.authenticated_remote_url(
            context.repository_full_name,
            access_token,
        )
        push_result = self._local_git.push(
            git_root,
            "origin",
            branch_name,
            authenticated_url,
        )
        if not push_result.success:
            return GitFinalizationResult(
                status=GitOperationStatus.FAILED,
                branch_name=branch_name,
                base_branch=base_branch,
                commit_sha=commit_result.commit_sha,
                title=title,
                failure_summary=push_result.message,
            )

        description = build_pull_request_description(
            PullRequestDescriptionContext(
                patch_plans=context.patch_plans,
                fix_attempts=context.fix_attempts,
                verification_results=context.verification_results,
                peer_reviews=context.peer_reviews,
                self_correction_cycles=context.self_correction_cycles,
                changed_files=context.changed_files,
            ),
        )
        pr_result = provider.create_pull_request(
            context.repository_full_name,
            branch_name,
            base_branch,
            title,
            description,
            access_token,
        )
        if not pr_result.success:
            return GitFinalizationResult(
                status=GitOperationStatus.FAILED,
                branch_name=branch_name,
                base_branch=base_branch,
                commit_sha=commit_result.commit_sha,
                push_commit_sha=push_result.commit_sha,
                title=title,
                description=description,
                failure_summary=pr_result.message,
            )

        return GitFinalizationResult(
            status=GitOperationStatus.PR_CREATED,
            branch_name=branch_name,
            base_branch=base_branch,
            commit_sha=commit_result.commit_sha,
            push_commit_sha=push_result.commit_sha,
            pull_request_url=pr_result.url,
            pull_request_number=pr_result.number,
            title=title,
            description=description,
        )

    def _prepare_git_root(
        self,
        workspace: RunWorkspace,
        changed_files: list[str],
    ) -> Path | None:
        candidates = [workspace.working, workspace.repository]
        git_root = next(
            (path for path in candidates if (path / ".git").exists()),
            None,
        )
        if git_root is None:
            return None

        source_root = workspace.working if workspace.working.exists() else workspace.repository
        if source_root != git_root:
            self._sync_changed_files(source_root, git_root, changed_files)
        elif source_root == workspace.working and workspace.repository.exists():
            self._sync_changed_files(workspace.working, workspace.repository, changed_files)
            if (workspace.repository / ".git").exists():
                git_root = workspace.repository

        return git_root

    @staticmethod
    def _sync_changed_files(source_root: Path, target_root: Path, changed_files: list[str]) -> None:
        for relative_path in changed_files:
            source = source_root / relative_path
            if not source.is_file():
                continue
            destination = target_root / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
