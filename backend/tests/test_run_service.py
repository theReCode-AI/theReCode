from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.db.repositories.run_repository import RunRepository
from app.models.project_intelligence import ProjectIntelligence
from app.models.run import Run, RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from app.workspace.constants import RUN_DIRECTORIES
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository


class InMemoryRunRepository(RunRepository):
    def __init__(self) -> None:
        self._runs: dict[str, dict] = {}

    def get_by_id_for_user(self, run_id: str, user_id: str) -> Run | None:
        document = self._runs.get(run_id)
        if document is None or str(document["user_id"]) != user_id:
            return None
        return Run.from_document(document.copy())

    def list_by_project(self, project_id: str, user_id: str) -> list[Run]:
        return [
            Run.from_document(document.copy())
            for document in self._runs.values()
            if str(document["project_id"]) == project_id and str(document["user_id"]) == user_id
        ]

    def create(
        self,
        run_id: str,
        project_id: str,
        user_id: str,
        repository_id: str | None,
        workspace_path: str,
        status: RunStatus = RunStatus.CREATED,
    ) -> Run:
        now = datetime.now(UTC)
        document = {
            "_id": ObjectId(run_id),
            "project_id": ObjectId(project_id),
            "user_id": ObjectId(user_id),
            "repository_id": ObjectId(repository_id) if repository_id else None,
            "status": status.value,
            "workspace_path": workspace_path,
            "created_at": now,
            "updated_at": now,
        }
        self._runs[run_id] = document
        return Run.from_document(document.copy())

    def update_status(self, run_id: str, user_id: str, status: RunStatus) -> Run | None:
        document = self._runs.get(run_id)
        if document is None or str(document["user_id"]) != user_id:
            return None
        document["status"] = status.value
        document["updated_at"] = datetime.now(UTC)
        return Run.from_document(document.copy())

    def update_project_intelligence(
        self,
        run_id: str,
        user_id: str,
        intelligence: ProjectIntelligence,
        status: RunStatus,
    ) -> Run | None:
        document = self._runs.get(run_id)
        if document is None or str(document["user_id"]) != user_id:
            return None
        now = datetime.now(UTC)
        document["project_intelligence"] = intelligence.model_dump(mode="json")
        document["analyzed_at"] = now
        document["status"] = status.value
        document["updated_at"] = now
        return Run.from_document(document.copy())


@pytest.fixture
def run_service(tmp_path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    from app.services.project_service import ProjectService

    project_service = ProjectService(project_repository, linked_repository_repository)
    workspace_manager = WorkspaceManager(tmp_path)
    service = RunService(
        run_repository=InMemoryRunRepository(),
        project_service=project_service,
        workspace_manager=workspace_manager,
    )
    return service, project_service, workspace_manager


def test_create_run_creates_workspace(run_service) -> None:
    service, project_service, workspace_manager = run_service
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Run Project"))

    run = service.create_run(user_id, RunCreate(project_id=project.id))

    assert run.status == RunStatus.CREATED
    workspace = workspace_manager.get_run_workspace(run.id)
    assert workspace.repository.is_dir()
    assert len(RUN_DIRECTORIES) == 7


def test_get_run_workspace_response(run_service) -> None:
    service, project_service, _workspace_manager = run_service
    user_id = str(ObjectId())
    from app.schemas.project import ProjectCreate

    project = project_service.create_project(user_id, ProjectCreate(name="Workspace Project"))
    run = service.create_run(user_id, RunCreate(project_id=project.id))

    workspace_response = service.get_run_workspace(user_id, run.id)

    assert workspace_response.run_id == run.id
    assert workspace_response.repository.endswith("/repository")
