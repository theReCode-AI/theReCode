"""Local git CLI operations used during finalization."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.git.types import BranchResult, CommitResult, GitOperationResult, PushResult


class LocalGitClient:
    """Execute local git commands against a repository working tree."""

    def get_current_branch(self, repo_path: Path) -> str | None:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def get_commit(self, repo_path: Path) -> str | None:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def create_branch(self, repo_path: Path, branch_name: str) -> BranchResult:
        checkout = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if checkout.returncode != 0:
            return BranchResult(
                success=False,
                branch_name=branch_name,
                message=checkout.stderr.strip() or "Failed to create branch",
            )
        return BranchResult(success=True, branch_name=branch_name)

    def stage_files(self, repo_path: Path, files: list[str]) -> GitOperationResult:
        if not files:
            return GitOperationResult(success=False, message="No files to stage")

        result = subprocess.run(
            ["git", "add", "--", *files],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return GitOperationResult(
                success=False,
                message=result.stderr.strip() or "Failed to stage files",
            )
        return GitOperationResult(success=True)

    def stage_all(self, repo_path: Path) -> GitOperationResult:
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return GitOperationResult(
                success=False,
                message=result.stderr.strip() or "Failed to stage files",
            )
        return GitOperationResult(success=True)

    def list_changed_files(self, repo_path: Path) -> list[str]:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []

        changed_files: list[str] = []
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", maxsplit=1)[1]
            if path:
                changed_files.append(path)
        return changed_files

    def commit(self, repo_path: Path, message: str, *, allow_empty: bool = False) -> CommitResult:
        command = ["git", "commit", "-m", message]
        if allow_empty:
            command.insert(2, "--allow-empty")
        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return CommitResult(
                success=False,
                message=result.stderr.strip() or "Failed to create commit",
            )
        return CommitResult(success=True, commit_sha=self.get_commit(repo_path))

    def push(
        self,
        repo_path: Path,
        remote: str,
        branch_name: str,
        authenticated_url: str,
    ) -> PushResult:
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", "push", authenticated_url, f"HEAD:refs/heads/{branch_name}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if result.returncode != 0:
            return PushResult(
                success=False,
                message=result.stderr.strip() or "Failed to push branch",
            )
        return PushResult(success=True, commit_sha=self.get_commit(repo_path))
