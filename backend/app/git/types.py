from dataclasses import dataclass
from pathlib import Path

from app.models.repository import GitProvider


@dataclass(frozen=True)
class RepositoryValidationResult:
    valid: bool
    provider: GitProvider
    full_name: str
    default_branch: str
    clone_url: str
    html_url: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class CloneResult:
    success: bool
    destination: Path
    branch: str
    commit_sha: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class GitOperationResult:
    success: bool
    message: str | None = None


@dataclass(frozen=True)
class BranchResult:
    success: bool
    branch_name: str
    message: str | None = None


@dataclass(frozen=True)
class CommitResult:
    success: bool
    commit_sha: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class PushResult:
    success: bool
    commit_sha: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class PullRequestResult:
    success: bool
    url: str | None = None
    number: int | None = None
    message: str | None = None
