from pathlib import Path

from app.core.config import Settings
from app.core.logging import get_logger
from app.git import GitProviderFactory
from app.git.types import CloneResult, RepositoryValidationResult
from app.models.run import RunStatus
from app.schemas.project import RepositoryResponse
from app.services.git_credential_service import GitCredentialService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager

logger = get_logger(__name__)


class GitService:
    """Orchestrate Git provider operations for linked repositories."""

    def __init__(
        self,
        project_service: ProjectService,
        git_credential_service: GitCredentialService,
        provider_factory: GitProviderFactory,
        workspace_manager: WorkspaceManager,
        run_service: RunService | None = None,
        app_settings: Settings | None = None,
    ) -> None:
        self._project_service = project_service
        self._git_credential_service = git_credential_service
        self._provider_factory = provider_factory
        self._workspace_manager = workspace_manager
        self._run_service = run_service
        self._settings = app_settings

    def validate_linked_repository(
        self,
        user_id: str,
        project_id: str,
        repository_id: str,
    ) -> RepositoryValidationResult:
        repository = self._get_linked_repository(user_id, project_id, repository_id)
        access_token = self._git_credential_service.get_access_token(user_id, repository.provider)
        provider = self._provider_factory.get_provider(repository.provider)
        result = provider.validate_repository(repository.full_name, access_token)

        logger.info(
            "Repository validation completed",
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "repository_id": repository_id,
                "valid": result.valid,
                "stage": "git_validate",
            },
        )
        return result

    def clone_linked_repository(
        self,
        user_id: str,
        project_id: str,
        repository_id: str,
        branch: str | None = None,
        run_id: str | None = None,
    ) -> CloneResult:
        repository = self._get_linked_repository(user_id, project_id, repository_id)
        destination = self._resolve_clone_destination(user_id, project_id, repository_id, run_id)
        return self._clone_repository(
            user_id=user_id,
            repository=repository,
            destination=destination,
            branch=branch,
            run_id=run_id,
            project_id=project_id,
            repository_id=repository_id,
        )

    def clone_run_repository(
        self,
        user_id: str,
        run_id: str,
        branch: str | None = None,
    ) -> CloneResult:
        if self._run_service is None:
            raise RuntimeError("Run service is not configured")

        run = self._run_service.get_run(user_id, run_id)
        if run.repository_id is None:
            return CloneResult(
                success=False,
                destination=self._workspace_manager.get_run_workspace(run_id).repository,
                branch=branch or "main",
                message="Run has no linked repository",
            )

        repository = self._get_linked_repository(user_id, run.project_id, run.repository_id)
        workspace = self._workspace_manager.get_run_workspace(run_id)
        self._run_service.update_status(user_id, run_id, RunStatus.CLONING)

        result = self._clone_repository(
            user_id=user_id,
            repository=repository,
            destination=workspace.repository,
            branch=branch,
            run_id=run_id,
            project_id=run.project_id,
            repository_id=run.repository_id,
        )

        if result.success:
            self._run_service.update_status(user_id, run_id, RunStatus.CREATED)

        return result

    def _clone_repository(
        self,
        user_id: str,
        repository: RepositoryResponse,
        destination: Path,
        branch: str | None,
        run_id: str | None,
        project_id: str,
        repository_id: str,
    ) -> CloneResult:
        access_token = self._git_credential_service.get_access_token(user_id, repository.provider)
        provider = self._provider_factory.get_provider(repository.provider)

        validation = provider.validate_repository(repository.full_name, access_token)
        if not validation.valid:
            return CloneResult(
                success=False,
                destination=destination,
                branch=branch or repository.default_branch,
                message=validation.message or "Repository validation failed",
            )

        target_branch = branch or validation.default_branch or repository.default_branch
        if destination.exists():
            self._clear_directory(destination)

        result = provider.clone_repository(
            repository.full_name,
            target_branch,
            access_token,
            destination,
        )

        logger.info(
            "Repository clone completed",
            extra={
                "user_id": user_id,
                "project_id": project_id,
                "repository_id": repository_id,
                "run_id": run_id,
                "success": result.success,
                "stage": "git_clone",
            },
        )
        return result

    def _resolve_clone_destination(
        self,
        user_id: str,
        project_id: str,
        repository_id: str,
        run_id: str | None,
    ) -> Path:
        if run_id:
            if self._run_service is None:
                raise RuntimeError("Run service is required when run_id is provided")
            workspace = self._run_service.get_workspace_for_run(user_id, run_id)
            return workspace.repository

        if self._settings is None:
            raise RuntimeError("Application settings are required for legacy clone paths")

        return (
            self._settings.resolved_workspace_root
            / "clones"
            / user_id
            / repository_id
            / "repository"
        )

    @staticmethod
    def _clear_directory(path: Path) -> None:
        import shutil

        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    def _get_linked_repository(
        self,
        user_id: str,
        project_id: str,
        repository_id: str,
    ) -> RepositoryResponse:
        return self._project_service.get_repository(user_id, project_id, repository_id)
