from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.db.repositories.linked_repository_repository import (
    LinkedRepositoryExistsError,
    LinkedRepositoryRepository,
)
from app.db.repositories.project_repository import (
    ProjectNameExistsError,
    ProjectRepository,
)
from app.models.project import Project
from app.models.repository import GitProvider, Repository
from app.schemas.project import ProjectCreate, ProjectUpdate, RepositoryCreate, RepositoryUpdate
from app.services.project_service import ProjectService


class InMemoryProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self._projects: dict[str, dict] = {}

    def list_by_user(self, user_id: str) -> list[Project]:
        return [
            Project.from_document(document.copy())
            for document in self._projects.values()
            if str(document["user_id"]) == user_id
        ]

    def get_by_id_for_user(self, project_id: str, user_id: str) -> Project | None:
        document = self._projects.get(project_id)
        if document is None or str(document["user_id"]) != user_id:
            return None
        return Project.from_document(document.copy())

    def create(self, user_id: str, name: str, description: str | None) -> Project:
        for document in self._projects.values():
            if str(document["user_id"]) == user_id and document["name"] == name.strip():
                raise ProjectNameExistsError(name)

        project_id = str(ObjectId())
        now = datetime.now(UTC)
        document = {
            "_id": ObjectId(project_id),
            "user_id": ObjectId(user_id),
            "name": name.strip(),
            "description": description,
            "created_at": now,
            "updated_at": now,
        }
        self._projects[project_id] = document
        return Project.from_document(document.copy())

    def update(
        self,
        project_id: str,
        user_id: str,
        name: str | None,
        description: str | None | object = ...,
    ) -> Project | None:
        document = self._projects.get(project_id)
        if document is None or str(document["user_id"]) != user_id:
            return None

        if name is not None:
            for other in self._projects.values():
                if (
                    str(other["user_id"]) == user_id
                    and other["name"] == name.strip()
                    and str(other["_id"]) != project_id
                ):
                    raise ProjectNameExistsError(name)
            document["name"] = name.strip()
        if description is not ...:
            document["description"] = description
        document["updated_at"] = datetime.now(UTC)
        return Project.from_document(document.copy())

    def delete(self, project_id: str, user_id: str) -> bool:
        document = self._projects.get(project_id)
        if document is None or str(document["user_id"]) != user_id:
            return False
        del self._projects[project_id]
        return True


class InMemoryLinkedRepositoryRepository(LinkedRepositoryRepository):
    def __init__(self) -> None:
        self._repositories: dict[str, dict] = {}

    def list_by_project(self, project_id: str) -> list[Repository]:
        return [
            Repository.from_document(document.copy())
            for document in self._repositories.values()
            if str(document["project_id"]) == project_id
        ]

    def get_by_id_for_project(self, repository_id: str, project_id: str) -> Repository | None:
        document = self._repositories.get(repository_id)
        if document is None or str(document["project_id"]) != project_id:
            return None
        return Repository.from_document(document.copy())

    def create(
        self,
        project_id: str,
        provider: GitProvider,
        full_name: str,
        default_branch: str,
        clone_url: str | None,
    ) -> Repository:
        for document in self._repositories.values():
            if (
                str(document["project_id"]) == project_id
                and document["provider"] == provider
                and document["full_name"] == full_name.strip()
            ):
                raise LinkedRepositoryExistsError(full_name, provider)

        repository_id = str(ObjectId())
        now = datetime.now(UTC)
        document = {
            "_id": ObjectId(repository_id),
            "project_id": ObjectId(project_id),
            "provider": provider,
            "full_name": full_name.strip(),
            "default_branch": default_branch.strip(),
            "clone_url": clone_url,
            "created_at": now,
            "updated_at": now,
        }
        self._repositories[repository_id] = document
        return Repository.from_document(document.copy())

    def update(
        self,
        repository_id: str,
        project_id: str,
        default_branch: str | None,
        clone_url: str | None | object = ...,
    ) -> Repository | None:
        document = self._repositories.get(repository_id)
        if document is None or str(document["project_id"]) != project_id:
            return None

        if default_branch is not None:
            document["default_branch"] = default_branch.strip()
        if clone_url is not ...:
            document["clone_url"] = clone_url
        document["updated_at"] = datetime.now(UTC)
        return Repository.from_document(document.copy())

    def delete(self, repository_id: str, project_id: str) -> bool:
        document = self._repositories.get(repository_id)
        if document is None or str(document["project_id"]) != project_id:
            return False
        del self._repositories[repository_id]
        return True

    def delete_by_project(self, project_id: str) -> int:
        to_delete = [
            repository_id
            for repository_id, document in self._repositories.items()
            if str(document["project_id"]) == project_id
        ]
        for repository_id in to_delete:
            del self._repositories[repository_id]
        return len(to_delete)


@pytest.fixture
def project_repository() -> InMemoryProjectRepository:
    return InMemoryProjectRepository()


@pytest.fixture
def linked_repository_repository() -> InMemoryLinkedRepositoryRepository:
    return InMemoryLinkedRepositoryRepository()


@pytest.fixture
def project_service(
    project_repository: InMemoryProjectRepository,
    linked_repository_repository: InMemoryLinkedRepositoryRepository,
) -> ProjectService:
    return ProjectService(
        project_repository=project_repository,
        linked_repository_repository=linked_repository_repository,
    )


def test_create_and_list_projects(project_service: ProjectService) -> None:
    user_id = str(ObjectId())
    project = project_service.create_project(
        user_id,
        ProjectCreate(name="Demo Project", description="A demo"),
    )

    projects = project_service.list_projects(user_id)

    assert len(projects) == 1
    assert projects[0].id == project.id
    assert projects[0].name == "Demo Project"


def test_user_cannot_access_other_users_project(project_service: ProjectService) -> None:
    owner_id = str(ObjectId())
    other_user_id = str(ObjectId())
    project = project_service.create_project(owner_id, ProjectCreate(name="Private"))

    from app.db.repositories.project_repository import ProjectNotFoundError

    with pytest.raises(ProjectNotFoundError):
        project_service.get_project(other_user_id, project.id)


def test_update_project(project_service: ProjectService) -> None:
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Old Name"))

    updated = project_service.update_project(
        user_id,
        project.id,
        ProjectUpdate(name="New Name", description="Updated"),
    )

    assert updated.name == "New Name"
    assert updated.description == "Updated"


def test_delete_project_cascades_repositories(
    project_service: ProjectService,
    linked_repository_repository: InMemoryLinkedRepositoryRepository,
) -> None:
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Cascade"))
    project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="github", full_name="org/repo"),
    )

    project_service.delete_project(user_id, project.id)

    assert linked_repository_repository.list_by_project(project.id) == []


def test_repository_crud(project_service: ProjectService) -> None:
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Repo Project"))

    created = project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="gitlab", full_name="group/service", default_branch="develop"),
    )
    updated = project_service.update_repository(
        user_id,
        project.id,
        created.id,
        RepositoryUpdate(default_branch="main"),
    )
    repositories = project_service.list_repositories(user_id, project.id)

    assert updated.default_branch == "main"
    assert len(repositories) == 1

    project_service.delete_repository(user_id, project.id, created.id)
    assert project_service.list_repositories(user_id, project.id) == []
