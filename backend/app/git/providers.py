import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from app.git.normalize import normalize_repository_full_name
from app.git.types import (
    CloneResult,
    GitOperationResult,
    PullRequestResult,
    RepositoryValidationResult,
)
from app.models.repository import GitProvider


class GitProviderClient(ABC):
    """Provider abstraction for Git hosting platforms."""

    provider: GitProvider

    @abstractmethod
    def validate_repository(
        self,
        full_name: str,
        access_token: str,
    ) -> RepositoryValidationResult:
        """Validate repository access and return metadata."""

    @abstractmethod
    def clone_repository(
        self,
        full_name: str,
        branch: str,
        access_token: str,
        destination: Path,
    ) -> CloneResult:
        """Clone repository to destination using Git CLI."""

    def checkout_branch(self, repo_path: Path, branch: str) -> GitOperationResult:
        result = subprocess.run(
            ["git", "checkout", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return GitOperationResult(success=False, message=result.stderr.strip())
        return GitOperationResult(success=True)

    @abstractmethod
    def create_pull_request(
        self,
        full_name: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        access_token: str,
    ) -> PullRequestResult:
        """Open a pull/merge request for the pushed branch."""

    def authenticated_remote_url(self, full_name: str, access_token: str) -> str:
        raise NotImplementedError

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

    def _run_git_clone(self, authenticated_url: str, branch: str, destination: Path) -> CloneResult:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            return CloneResult(
                success=False,
                destination=destination,
                branch=branch,
                message="Destination path already exists",
            )

        clone_command = [
            "git",
            "clone",
            "--branch",
            branch,
            "--depth",
            "1",
            authenticated_url,
            str(destination),
        ]
        result = subprocess.run(
            clone_command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return CloneResult(
                success=False,
                destination=destination,
                branch=branch,
                message=result.stderr.strip() or "Git clone failed",
            )

        return CloneResult(
            success=True,
            destination=destination,
            branch=branch,
            commit_sha=self.get_commit(destination),
        )


class GitHubProvider(GitProviderClient):
    provider: GitProvider = "github"

    def __init__(self, api_base_url: str, http_client: httpx.Client | None = None) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=30.0)

    def validate_repository(
        self,
        full_name: str,
        access_token: str,
    ) -> RepositoryValidationResult:
        full_name = normalize_repository_full_name(self.provider, full_name)
        response = self._http_client.get(
            f"{self._api_base_url}/repos/{full_name}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status_code != 200:
            return RepositoryValidationResult(
                valid=False,
                provider=self.provider,
                full_name=full_name,
                default_branch="main",
                clone_url="",
                message="Repository not found or access denied",
            )

        payload = response.json()
        return RepositoryValidationResult(
            valid=True,
            provider=self.provider,
            full_name=payload["full_name"],
            default_branch=payload.get("default_branch") or "main",
            clone_url=payload["clone_url"],
            html_url=payload.get("html_url"),
        )

    def clone_repository(
        self,
        full_name: str,
        branch: str,
        access_token: str,
        destination: Path,
    ) -> CloneResult:
        full_name = normalize_repository_full_name(self.provider, full_name)
        authenticated_url = self.authenticated_remote_url(full_name, access_token)
        return self._run_git_clone(authenticated_url, branch, destination)

    def authenticated_remote_url(self, full_name: str, access_token: str) -> str:
        return f"https://x-access-token:{access_token}@github.com/{full_name}.git"

    def create_pull_request(
        self,
        full_name: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        access_token: str,
    ) -> PullRequestResult:
        full_name = normalize_repository_full_name(self.provider, full_name)
        response = self._http_client.post(
            f"{self._api_base_url}/repos/{full_name}/pulls",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
            },
        )
        if response.status_code not in {200, 201}:
            message = response.json().get("message") if response.content else "Pull request failed"
            return PullRequestResult(success=False, message=message)

        payload = response.json()
        return PullRequestResult(
            success=True,
            url=payload.get("html_url"),
            number=payload.get("number"),
        )


class GitLabProvider(GitProviderClient):
    provider: GitProvider = "gitlab"

    def __init__(self, api_base_url: str, http_client: httpx.Client | None = None) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=30.0)

    def validate_repository(
        self,
        full_name: str,
        access_token: str,
    ) -> RepositoryValidationResult:
        encoded_path = full_name.replace("/", "%2F")
        response = self._http_client.get(
            f"{self._api_base_url}/projects/{encoded_path}",
            headers={"PRIVATE-TOKEN": access_token},
        )
        if response.status_code != 200:
            return RepositoryValidationResult(
                valid=False,
                provider=self.provider,
                full_name=full_name,
                default_branch="main",
                clone_url="",
                message="Repository not found or access denied",
            )

        payload = response.json()
        return RepositoryValidationResult(
            valid=True,
            provider=self.provider,
            full_name=payload["path_with_namespace"],
            default_branch=payload.get("default_branch") or "main",
            clone_url=payload["http_url_to_repo"],
            html_url=payload.get("web_url"),
        )

    def clone_repository(
        self,
        full_name: str,
        branch: str,
        access_token: str,
        destination: Path,
    ) -> CloneResult:
        full_name = normalize_repository_full_name(self.provider, full_name)
        authenticated_url = self.authenticated_remote_url(full_name, access_token)
        return self._run_git_clone(authenticated_url, branch, destination)

    def authenticated_remote_url(self, full_name: str, access_token: str) -> str:
        return f"https://oauth2:{access_token}@gitlab.com/{full_name}.git"

    def create_pull_request(
        self,
        full_name: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
        access_token: str,
    ) -> PullRequestResult:
        full_name = normalize_repository_full_name(self.provider, full_name)
        encoded_path = full_name.replace("/", "%2F")
        response = self._http_client.post(
            f"{self._api_base_url}/projects/{encoded_path}/merge_requests",
            headers={"PRIVATE-TOKEN": access_token},
            json={
                "title": title,
                "description": body,
                "source_branch": head_branch,
                "target_branch": base_branch,
            },
        )
        if response.status_code not in {200, 201}:
            message = response.json().get("message") if response.content else "Merge request failed"
            return PullRequestResult(success=False, message=message)

        payload = response.json()
        return PullRequestResult(
            success=True,
            url=payload.get("web_url"),
            number=payload.get("iid"),
        )


class UnsupportedGitProviderError(Exception):
    def __init__(self, provider: str) -> None:
        super().__init__(f"Unsupported git provider: {provider}")


class GitProviderFactory:
    """Create provider clients for supported Git hosts."""

    def __init__(
        self,
        github_api_base_url: str,
        gitlab_api_base_url: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._github_api_base_url = github_api_base_url
        self._gitlab_api_base_url = gitlab_api_base_url
        self._http_client = http_client

    def get_provider(self, provider: GitProvider) -> GitProviderClient:
        if provider == "github":
            return GitHubProvider(self._github_api_base_url, self._http_client)
        if provider == "gitlab":
            return GitLabProvider(self._gitlab_api_base_url, self._http_client)
        raise UnsupportedGitProviderError(provider)
