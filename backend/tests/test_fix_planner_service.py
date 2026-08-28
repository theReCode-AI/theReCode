import shutil
from pathlib import Path

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.models.issue_group_enums import IssueGroupStatus
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate
from app.schemas.run import RunCreate
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.fix_planner_service import (
    FIX_PLANS_ARTIFACT_NAME,
    FixPlannerService,
    IssueGroupsRequiredError,
)
from app.services.issue_correlation_service import IssueCorrelationService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_mock_command_runner
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_finding_repository import InMemoryFindingRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_issue_group_repository import InMemoryIssueGroupRepository
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_run_service import InMemoryRunRepository


@pytest.fixture
def fix_planner_stack(tmp_path: Path):
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    finding_repository = InMemoryFindingRepository()
    issue_group_repository = InMemoryIssueGroupRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
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
    planner_service = FixPlannerService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        fix_plan_repository=fix_plan_repository,
        event_repository=event_repository,
    )

    return (
        planner_service,
        correlation_service,
        diagnostic_agent_service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        issue_group_repository,
        fix_plan_repository,
        event_repository,
        finding_repository,
    )


def _seed_repository(workspace_manager: WorkspaceManager, run_id: str) -> None:
    workspace = workspace_manager.get_run_workspace(run_id)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.repository,
        dirs_exist_ok=True,
    )


def test_plan_run_persists_patch_plans(
    fix_planner_stack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.models.finding import Finding
    from app.models.finding_enums import (
        DiagnosticAgentName,
        FindingFixability,
        FindingSeverity,
        FindingStatus,
    )

    (
        planner_service,
        correlation_service,
        diagnostic_agent_service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        issue_group_repository,
        fix_plan_repository,
        event_repository,
        finding_repository,
    ) = fix_planner_stack
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Planner Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))
    _seed_repository(workspace_manager, run.id)

    now = datetime.now(UTC)
    finding = Finding(
        finding_id=str(ObjectId()),
        run_id=run.id,
        agent=DiagnosticAgentName.CODE_QUALITY,
        tool="ruff",
        category="unused_variable",
        severity=FindingSeverity.LOW,
        confidence=0.9,
        file="src/main.py",
        line_start=10,
        line_end=10,
        message="unused variable",
        rule_id="F841",
        evidence="unused variable",
        fixability=FindingFixability.AGENT,
        status=FindingStatus.OPEN,
        created_at=now,
    )
    finding_repository.replace_for_run(run.id, [finding])
    correlation_service.correlate_run(user_id, run.id)

    response = planner_service.plan_run(user_id, run.id)

    assert response.run_id == run.id
    assert response.patch_plan_count == 1
    assert len(fix_plan_repository.list_by_run(run.id)) == 1

    workspace = workspace_manager.get_run_workspace(run.id)
    assert (workspace.baseline / FIX_PLANS_ARTIFACT_NAME).is_file()

    stored_run = run_repository.get_by_id_for_user(run.id, user_id)
    assert stored_run is not None
    assert stored_run.status == RunStatus.PLANNING

    if response.patch_plan_count:
        groups = issue_group_repository.list_by_run(run.id)
        assert all(group.status == IssueGroupStatus.PLANNED for group in groups)

    events = [
        event
        for event in event_repository.list_by_run(run.id)
        if event.event_type.value == "FIX_PLAN_CREATED"
    ]
    assert len(events) == response.patch_plan_count


def test_plan_run_requires_prior_correlation(fix_planner_stack) -> None:
    (
        planner_service,
        _correlation_service,
        _diagnostic_agent_service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _issue_group_repository,
        _fix_plan_repository,
        _event_repository,
        _finding_repository,
    ) = fix_planner_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="No Groups"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(IssueGroupsRequiredError):
        planner_service.plan_run(user_id, run.id)
