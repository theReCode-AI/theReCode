import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.adk.workflows.root_orchestrator import RootOrchestrator
from app.core.config import Settings
from app.models.agent_event import AgentEventType
from app.models.agent_state import OrchestrationStatus
from app.models.finding_enums import DiagnosticAgentName
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.git_credential_service import GitCredentialService
from app.services.git_service import GitService
from app.services.project_intelligence_service import ProjectIntelligenceService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_mock_command_runner
from tests.test_agent_orchestration_repository import (
    InMemoryAgentEventRepository,
    InMemoryAgentStateRepository,
)
from tests.test_finding_repository import InMemoryFindingRepository
from tests.test_git_service import InMemoryGitCredentialRepository
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository


@pytest.fixture
def orchestrator_stack(tmp_path: Path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    event_repository = InMemoryAgentEventRepository()
    state_repository = InMemoryAgentStateRepository()
    finding_repository = InMemoryFindingRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    settings = Settings(environment="test", scanner_timeout_seconds=30)

    project_service = ProjectService(project_repository, linked_repository_repository)
    run_service = RunService(run_repository, project_service, workspace_manager)
    intelligence_service = ProjectIntelligenceService(run_repository, run_service)
    diagnostic_agent_service = DiagnosticAgentService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        app_settings=settings,
        command_runner=build_mock_command_runner(),
    )
    git_service = GitService(
        project_service=project_service,
        git_credential_service=GitCredentialService(
            InMemoryGitCredentialRepository(),
            settings,
        ),
        provider_factory=MagicMock(),
        workspace_manager=workspace_manager,
        run_service=run_service,
        app_settings=settings,
    )
    orchestrator = RootOrchestrator(
        run_repository=run_repository,
        run_service=run_service,
        git_service=git_service,
        intelligence_service=intelligence_service,
        diagnostic_agent_service=diagnostic_agent_service,
        event_repository=event_repository,
        state_repository=state_repository,
    )

    return (
        orchestrator,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        event_repository,
        state_repository,
    )


def _seed_repository(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.repository,
        dirs_exist_ok=True,
    )


def test_root_orchestrator_completes_baseline_lifecycle(
    orchestrator_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        orchestrator,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        event_repository,
        state_repository,
    ) = orchestrator_stack
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Orchestration Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    state = orchestrator.execute(
        user_id,
        run.id,
        skip_clone=True,
        agents=[DiagnosticAgentName.CODE_QUALITY, DiagnosticAgentName.TEST],
    )

    assert state.status == OrchestrationStatus.COMPLETED
    assert state.progress == 100
    assert "project_intelligence" in state.completed_stages
    assert "diagnostics" in state.completed_stages
    assert "code_quality_agent" in state.completed_agents
    assert "test_agent" in state.completed_agents

    events = event_repository.list_by_run(run.id)
    event_types = [event.event_type for event in events]
    assert AgentEventType.RUN_CREATED in event_types
    assert AgentEventType.PROJECT_ANALYSIS_COMPLETED in event_types
    assert AgentEventType.AGENT_COMPLETED in event_types
    assert AgentEventType.RUN_COMPLETED in event_types

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.DIAGNOSING


def test_root_orchestrator_fails_without_repository(
    orchestrator_stack,
) -> None:
    (
        orchestrator,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        event_repository,
        _state_repository,
    ) = orchestrator_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Empty Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    state = orchestrator.execute(user_id, run.id, skip_clone=True)

    assert state.status == OrchestrationStatus.FAILED
    assert state.error_message is not None

    events = event_repository.list_by_run(run.id)
    assert any(event.event_type == AgentEventType.RUN_FAILED for event in events)
