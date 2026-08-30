from app.core.logging import get_logger
from app.db.repositories.linked_repository_repository import (
    LinkedRepositoryNotFoundError,
    LinkedRepositoryRepository,
)
from app.db.repositories.project_repository import (
    ProjectNotFoundError,
    ProjectRepository,
)
from app.models.project import Project
from app.models.repository import Repository
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    RepositoryCreate,
    RepositoryResponse,
    RepositoryUpdate,
)

logger = get_logger(__name__)


class ProjectService:
    """User-scoped project management."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        linked_repository_repository: LinkedRepositoryRepository,
    ) -> None:
        self._project_repository = project_repository
        self._linked_repository_repository = linked_repository_repository

    def create_project(self, user_id: str, payload: ProjectCreate) -> ProjectResponse:
        project = self._project_repository.create(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
        )
        logger.info(
            "Project created",
            extra={"project_id": project.id, "user_id": user_id, "stage": "project_create"},
        )
        return self._to_project_response(project)

    def list_projects(self, user_id: str) -> list[ProjectResponse]:
        projects = self._project_repository.list_by_user(user_id)
        return [self._to_project_response(project) for project in projects]

    def get_project(self, user_id: str, project_id: str) -> ProjectResponse:
        project = self._require_project(user_id, project_id)
        return self._to_project_response(project)

    def update_project(
        self,
        user_id: str,
        project_id: str,
        payload: ProjectUpdate,
    ) -> ProjectResponse:
        self._require_project(user_id, project_id)
        updates = payload.model_dump(exclude_unset=True)
        project = self._project_repository.update(
            project_id=project_id,
            user_id=user_id,
            name=updates.get("name"),
            description=updates.get("description", ...),
        )
        if project is None:
            raise ProjectNotFoundError(project_id)

        logger.info(
            "Project updated",
            extra={"project_id": project_id, "user_id": user_id, "stage": "project_update"},
        )
        return self._to_project_response(project)

    def delete_project(self, user_id: str, project_id: str) -> None:
        self._require_project(user_id, project_id)
        self._linked_repository_repository.delete_by_project(project_id)
        deleted = self._project_repository.delete(project_id, user_id)
        if not deleted:
            raise ProjectNotFoundError(project_id)

        logger.info(
            "Project deleted",
            extra={"project_id": project_id, "user_id": user_id, "stage": "project_delete"},
        )

    def create_repository(
        self,
        user_id: str,
        project_id: str,
        payload: RepositoryCreate,
    ) -> RepositoryResponse:
        self._require_project(user_id, project_id)
        repository = self._linked_repository_repository.create(
            project_id=project_id,
            provider=payload.provider,
            full_name=payload.full_name,
            default_branch=payload.default_branch,
            clone_url=payload.clone_url,
        )
        logger.info(
            "Repository linked",
            extra={
                "project_id": project_id,
                "repository_id": repository.id,
                "provider": repository.provider,
                "stage": "repository_create",
            },
        )
        return self._to_repository_response(repository)

    def list_repositories(self, user_id: str, project_id: str) -> list[RepositoryResponse]:
        self._require_project(user_id, project_id)
        repositories = self._linked_repository_repository.list_by_project(project_id)
        return [self._to_repository_response(repository) for repository in repositories]

    def get_repository(
        self,
        user_id: str,
        project_id: str,
        repository_id: str,
    ) -> RepositoryResponse:
        self._require_project(user_id, project_id)
        repository = self._linked_repository_repository.get_by_id_for_project(
            repository_id,
            project_id,
        )
        if repository is None:
            raise LinkedRepositoryNotFoundError(repository_id)
        return self._to_repository_response(repository)

    def update_repository(
        self,
        user_id: str,
        project_id: str,
        repository_id: str,
        payload: RepositoryUpdate,
    ) -> RepositoryResponse:
        self._require_project(user_id, project_id)
        updates = payload.model_dump(exclude_unset=True)
        repository = self._linked_repository_repository.update(
            repository_id=repository_id,
            project_id=project_id,
            default_branch=updates.get("default_branch"),
            clone_url=updates.get("clone_url", ...),
        )
        if repository is None:
            raise LinkedRepositoryNotFoundError(repository_id)

        logger.info(
            "Repository updated",
            extra={
                "project_id": project_id,
                "repository_id": repository_id,
                "stage": "repository_update",
            },
        )
        return self._to_repository_response(repository)

    def delete_repository(self, user_id: str, project_id: str, repository_id: str) -> None:
        self._require_project(user_id, project_id)
        deleted = self._linked_repository_repository.delete(repository_id, project_id)
        if not deleted:
            raise LinkedRepositoryNotFoundError(repository_id)

        logger.info(
            "Repository unlinked",
            extra={
                "project_id": project_id,
                "repository_id": repository_id,
                "stage": "repository_delete",
            },
        )

    def _require_project(self, user_id: str, project_id: str) -> Project:
        project = self._project_repository.get_by_id_for_user(project_id, user_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    @staticmethod
    def _to_project_response(project: Project) -> ProjectResponse:
        return ProjectResponse(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    def _to_repository_response(repository: Repository) -> RepositoryResponse:
        return RepositoryResponse(
            id=repository.id,
            project_id=repository.project_id,
            provider=repository.provider,
            full_name=repository.full_name,
            default_branch=repository.default_branch,
            clone_url=repository.clone_url,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        )
