import shutil
from pathlib import Path

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.issue_correlation_service import (
    ISSUE_GROUPS_ARTIFACT_NAME,
    IssueCorrelationService,
)
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_mock_command_runner
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_finding_repository import InMemoryFindingRepository
from tests.test_issue_group_repository import InMemoryIssueGroupRepository
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository


@pytest.fixture
def issue_correlation_stack(tmp_path: Path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    finding_repository = InMemoryFindingRepository()
    issue_group_repository = InMemoryIssueGroupRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    settings = Settings(environment="test", scanner_timeout_seconds=30)

    project_service = ProjectService(project_repository, linked_repository_repository)
    run_service = RunService(run_repository, project_service, workspace_manager)
    diagnostic_agent_service = DiagnosticAgentService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        app_settings=settings,
        command_runner=build_mock_command_runner(),
    )
    correlation_service = IssueCorrelationService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        event_repository=event_repository,
    )

    return (
        correlation_service,
        diagnostic_agent_service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        issue_group_repository,
        event_repository,
    )


def _seed_repository(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.repository,
        dirs_exist_ok=True,
    )


def test_correlate_run_persists_issue_groups(
    issue_correlation_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        correlation_service,
        diagnostic_agent_service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        issue_group_repository,
        event_repository,
    ) = issue_correlation_stack
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Correlation Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    diagnostic_agent_service.run_agents(
        user_id,
        run.id,
        agents=[DiagnosticAgentName.CODE_QUALITY, DiagnosticAgentName.TEST],
    )

    response = correlation_service.correlate_run(user_id, run.id)

    assert response.run_id == run.id
    assert response.issue_group_count >= 0
    assert len(issue_group_repository.list_by_run(run.id)) == response.issue_group_count

    workspace = workspace_manager.get_run_workspace(run.id)
    assert (workspace.baseline / ISSUE_GROUPS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.PLANNING

    events = event_repository.list_by_run(run.id)
    assert len(events) == response.issue_group_count


def test_list_issue_groups_returns_empty_before_correlation(issue_correlation_stack) -> None:
    (
        correlation_service,
        _diagnostic_agent_service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _issue_group_repository,
        _event_repository,
    ) = issue_correlation_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Empty Correlation"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    issue_groups = correlation_service.list_issue_groups(user_id, run.id)
    assert issue_groups == []
