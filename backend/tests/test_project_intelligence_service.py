import shutil
from pathlib import Path

import pytest
from bson import ObjectId

from app.db.repositories.run_repository import RunNotFoundError
from app.intelligence import RepositoryNotReadyError
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.project_intelligence_service import (
    INTELLIGENCE_ARTIFACT_NAME,
    ProjectIntelligenceService,
)
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository


@pytest.fixture
def intelligence_service(tmp_path: Path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    project_service = ProjectService(project_repository, linked_repository_repository)
    workspace_manager = WorkspaceManager(tmp_path)
    run_service = RunService(run_repository, project_service, workspace_manager)
    service = ProjectIntelligenceService(run_repository, run_service)
    return service, run_service, project_service, run_repository, workspace_manager


def _seed_repository(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.repository,
        dirs_exist_ok=True,
    )


def test_analyze_run_persists_intelligence(intelligence_service) -> None:
    service, run_service, project_service, run_repository, workspace_manager = intelligence_service
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Intel Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    result = service.analyze_run(user_id, run.id)

    assert result.run_id == run.id
    assert result.intelligence.frameworks == ["fastapi"]
    assert result.intelligence.package_manager.value == "uv"
    assert Path(result.artifact_path).name == INTELLIGENCE_ARTIFACT_NAME
    assert Path(result.artifact_path).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.ANALYZING
    assert stored_run.project_intelligence is not None
    assert stored_run.analyzed_at is not None


def test_get_intelligence_requires_analysis(intelligence_service) -> None:
    service, run_service, project_service, _, workspace_manager = intelligence_service
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Pending Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    with pytest.raises(RepositoryNotReadyError):
        service.get_intelligence(user_id, run.id)


def test_analyze_run_not_found(intelligence_service) -> None:
    service, _, _, _, _ = intelligence_service
    with pytest.raises(RunNotFoundError):
        service.analyze_run(str(ObjectId()), str(ObjectId()))
