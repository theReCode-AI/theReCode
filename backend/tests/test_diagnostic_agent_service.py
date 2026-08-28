import shutil
from pathlib import Path

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.diagnostic_agent_service import FINDINGS_ARTIFACT_NAME, DiagnosticAgentService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_mock_command_runner
from tests.test_finding_repository import InMemoryFindingRepository
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository


@pytest.fixture
def diagnostic_agent_service(tmp_path: Path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    finding_repository = InMemoryFindingRepository()
    project_service = ProjectService(project_repository, linked_repository_repository)
    workspace_manager = WorkspaceManager(tmp_path)
    run_service = RunService(run_repository, project_service, workspace_manager)
    settings = Settings(environment="test", scanner_timeout_seconds=30)
    service = DiagnosticAgentService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        app_settings=settings,
        command_runner=build_mock_command_runner(),
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        finding_repository,
        run_repository,
    )


def _seed_repository(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.repository,
        dirs_exist_ok=True,
    )


def test_run_agents_persists_findings(
    diagnostic_agent_service,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, run_service, project_service, workspace_manager, finding_repository, run_repository = (
        diagnostic_agent_service
    )
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Agent Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    response = service.run_agents(
        user_id,
        run.id,
        agents=[DiagnosticAgentName.CODE_QUALITY, DiagnosticAgentName.TEST],
    )

    assert response.run_id == run.id
    assert response.finding_count >= 0
    assert len(response.agents) == 2
    assert len(finding_repository.list_by_run(run.id)) == response.finding_count

    workspace = workspace_manager.get_run_workspace(run.id)
    assert (workspace.baseline / FINDINGS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.DIAGNOSING
