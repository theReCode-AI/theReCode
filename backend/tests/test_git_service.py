from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.db.repositories.git_credential_repository import GitCredentialRepository
from app.git.providers import GitProviderFactory
from app.git.types import CloneResult, RepositoryValidationResult
from app.schemas.git import GitCredentialCreate
from app.services.git_credential_service import GitCredentialService
from app.services.git_service import GitService
from app.services.project_service import ProjectService
from app.workspace import WorkspaceManager
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository


class InMemoryGitCredentialRepository(GitCredentialRepository):
    def __init__(self) -> None:
        self._credentials: dict[tuple[str, str], dict] = {}

    def list_by_user(self, user_id: str) -> list:
        from app.models.git_credential import GitCredential

        return [
            GitCredential.from_document(document.copy())
            for (stored_user_id, _), document in self._credentials.items()
            if stored_user_id == user_id
        ]

    def get_by_user_and_provider(self, user_id: str, provider: str):
        from app.models.git_credential import GitCredential

        document = self._credentials.get((user_id, provider))
        if document is None:
            return None
        return GitCredential.from_document(document.copy())

    def upsert(
        self,
        user_id: str,
        provider: str,
        encrypted_token: str,
        token_label: str | None,
    ):
        from app.models.git_credential import GitCredential

        now = datetime.now(UTC)
        key = (user_id, provider)
        existing = self._credentials.get(key)
        credential_id = existing["_id"] if existing else ObjectId()
        document = {
            "_id": credential_id,
            "user_id": ObjectId(user_id),
            "provider": provider,
            "encrypted_token": encrypted_token,
            "token_label": token_label,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self._credentials[key] = document
        return GitCredential.from_document(document.copy())

    def delete(self, user_id: str, provider: str) -> bool:
        return self._credentials.pop((user_id, provider), None) is not None


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        credentials_encryption_key="phase5-test-encryption-key-value",
    )


@pytest.fixture
def git_services(settings: Settings, tmp_path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    credential_repository = InMemoryGitCredentialRepository()
    project_service = ProjectService(project_repository, linked_repository_repository)
    git_credential_service = GitCredentialService(credential_repository, settings)
    provider_factory = MagicMock(spec=GitProviderFactory)
    workspace_manager = WorkspaceManager(tmp_path)
    git_service = GitService(
        project_service=project_service,
        git_credential_service=git_credential_service,
        provider_factory=provider_factory,
        workspace_manager=workspace_manager,
        app_settings=settings,
    )
    return project_service, git_credential_service, provider_factory, git_service


def test_git_credential_service_never_returns_token(git_services, settings) -> None:
    _, git_credential_service, _, _ = git_services
    user_id = str(ObjectId())

    response = git_credential_service.save_credential(
        user_id,
        GitCredentialCreate(provider="github", access_token="ghp_secret", token_label="dev"),
    )

    assert response.provider == "github"
    assert "ghp_secret" not in response.model_dump_json()


def test_validate_linked_repository(git_services) -> None:
    project_service, git_credential_service, provider_factory, git_service = git_services
    user_id = str(ObjectId())

    git_credential_service.save_credential(
        user_id,
        GitCredentialCreate(provider="github", access_token="ghp_secret"),
    )
    from app.schemas.project import ProjectCreate, RepositoryCreate

    project = project_service.create_project(user_id, ProjectCreate(name="Git Project"))
    repository = project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="github", full_name="org/repo"),
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

    result = git_service.validate_linked_repository(user_id, project.id, repository.id)

    assert result.valid is True
    mock_provider.validate_repository.assert_called_once_with("org/repo", "ghp_secret")


def test_clone_linked_repository(git_services, tmp_path) -> None:
    project_service, git_credential_service, provider_factory, git_service = git_services
    user_id = str(ObjectId())

    git_credential_service.save_credential(
        user_id,
        GitCredentialCreate(provider="github", access_token="ghp_secret"),
    )
    from app.schemas.project import ProjectCreate, RepositoryCreate

    project = project_service.create_project(user_id, ProjectCreate(name="Clone Project"))
    repository = project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="github", full_name="org/repo"),
    )

    mock_provider = MagicMock()
    mock_provider.validate_repository.return_value = RepositoryValidationResult(
        valid=True,
        provider="github",
        full_name="org/repo",
        default_branch="main",
        clone_url="https://github.com/org/repo.git",
    )
    mock_provider.clone_repository.return_value = CloneResult(
        success=True,
        destination=tmp_path / "clones" / user_id / repository.id / "repository",
        branch="main",
        commit_sha="abc123",
    )
    provider_factory.get_provider.return_value = mock_provider

    result = git_service.clone_linked_repository(user_id, project.id, repository.id)

    assert result.success is True
    assert result.commit_sha == "abc123"
