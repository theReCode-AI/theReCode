from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.models.git_operation import GitOperation
from app.models.git_operation_enums import GitOperationStatus
from app.models.run import RunStatus
from app.schemas.project import ProjectCreate, RepositoryCreate
from app.schemas.run import RunCreate
from app.services.project_service import ProjectService
from app.services.report_service import (
    RUN_REPORT_ARTIFACT_NAME,
    ReportService,
    RunNotReadyForReportError,
)
from app.services.run_service import RunService
from app.workspace import WorkspaceManager
from tests.test_agent_orchestration_repository import InMemoryAgentEventRepository
from tests.test_approval_repository import InMemoryApprovalRepository
from tests.test_finding_repository import InMemoryFindingRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_git_operation_repository import InMemoryGitOperationRepository
from tests.test_issue_group_repository import InMemoryIssueGroupRepository
from tests.test_memory_repository import InMemoryMemoryRepository
from tests.test_peer_review_result_repository import InMemoryPeerReviewResultRepository
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_regression_test_result_repository import InMemoryRegressionTestResultRepository
from tests.test_report_repository import InMemoryReportRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_self_correction_cycle_repository import InMemorySelfCorrectionCycleRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
def report_stack(tmp_path: Path):
    run_repository = InMemoryRunRepository()
    finding_repository = InMemoryFindingRepository()
    issue_group_repository = InMemoryIssueGroupRepository()
    fix_plan_repository = InMemoryFixPlanRepository()
    risk_decision_repository = InMemoryRiskDecisionRepository()
    fix_attempt_repository = InMemoryFixAttemptRepository()
    verification_result_repository = InMemoryVerificationResultRepository()
    self_correction_cycle_repository = InMemorySelfCorrectionCycleRepository()
    regression_test_result_repository = InMemoryRegressionTestResultRepository()
    peer_review_result_repository = InMemoryPeerReviewResultRepository()
    approval_repository = InMemoryApprovalRepository()
    memory_repository = InMemoryMemoryRepository()
    git_operation_repository = InMemoryGitOperationRepository()
    report_repository = InMemoryReportRepository()
    event_repository = InMemoryAgentEventRepository()
    workspace_manager = WorkspaceManager(tmp_path)
    project_service = ProjectService(
        InMemoryProjectRepository(),
        InMemoryLinkedRepositoryRepository(),
    )
    run_service = RunService(run_repository, project_service, workspace_manager)
    report_agent = MagicMock()
    service = ReportService(
        run_repository=run_repository,
        run_service=run_service,
        project_service=project_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        regression_test_result_repository=regression_test_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        approval_repository=approval_repository,
        memory_repository=memory_repository,
        git_operation_repository=git_operation_repository,
        report_repository=report_repository,
        event_repository=event_repository,
        report_agent=report_agent,
    )
    return (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        git_operation_repository,
        report_repository,
        event_repository,
        report_agent,
    )


def test_generate_run_report_requires_reporting_status(report_stack) -> None:
    service, run_service, project_service, *_ = report_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Report Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    with pytest.raises(RunNotReadyForReportError):
        service.generate_run_report(user_id, run.id)


def test_generate_run_report_persists_markdown_and_pdf(report_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        run_repository,
        git_operation_repository,
        report_repository,
        event_repository,
        report_agent,
    ) = report_stack

    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Report Project"))
    repository = project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="github", full_name="org/repo"),
    )
    run = run_service.create_run(
        user_id,
        RunCreate(project_id=project.id, repository_id=repository.id),
    )
    run_repository.update_status(run.id, user_id, RunStatus.REPORTING)
    now = datetime.now(UTC)
    git_operation_repository.add(
        GitOperation(
            git_operation_id=str(ObjectId()),
            run_id=run.id,
            project_id=project.id,
            repository_id=repository.id,
            provider="github",
            status=GitOperationStatus.PR_CREATED,
            branch_name="agent/run-security",
            base_branch="main",
            commit_sha="abc123",
            pull_request_url="https://github.com/org/repo/pull/1",
            pull_request_number=1,
            title="theReCode: Security issue",
            description="Body",
            changed_files=["src/auth.py"],
            created_at=now,
        ),
    )

    workspace = workspace_manager.get_run_workspace(run.id)
    markdown_path = workspace.reports / "run_report.md"
    pdf_path = workspace.reports / "run_report.pdf"
    generated = MagicMock()
    generated.markdown = "# Report"
    generated.plain_text_lines = ["Report"]
    generated.final_health_score = 90.0
    generated.pull_request_url = "https://github.com/org/repo/pull/1"
    generated.branch_name = "agent/run-security"
    generated.commit_sha = "abc123"
    generated.duration_ms = 1000
    generated.tool_versions = {"ruff": "0.8.0"}
    report_agent.generate.return_value = (
        generated,
        MagicMock(markdown_path=markdown_path, pdf_path=pdf_path),
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# Report", encoding="utf-8")
    pdf_path.write_bytes(b"%PDF-1.4 test")

    response = service.generate_run_report(user_id, run.id)

    assert response.run_status == RunStatus.COMPLETED.value
    assert report_repository.get_by_run(run.id) is not None
    assert (workspace.baseline / RUN_REPORT_ARTIFACT_NAME).is_file()
    events = event_repository.list_by_run(run.id)
    assert any(event.event_type.value == "REPORT_GENERATION_COMPLETED" for event in events)
    assert any(event.event_type.value == "RUN_COMPLETED" for event in events)


def test_get_run_report_loads_from_workspace_artifact_when_db_empty(report_stack) -> None:
    (
        service,
        run_service,
        project_service,
        workspace_manager,
        _run_repository,
        _git_operation_repository,
        report_repository,
        _event_repository,
        report_agent,
    ) = report_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Report Project"))
    repository = project_service.create_repository(
        user_id,
        project.id,
        RepositoryCreate(provider="github", full_name="org/repo", default_branch="main"),
    )
    run = run_service.create_run(
        user_id,
        RunCreate(project_id=project.id, repository_id=repository.id),
    )

    workspace = workspace_manager.get_run_workspace(run.id)
    markdown_path = workspace.reports / "run_report.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# Workspace report", encoding="utf-8")
    artifact_payload = {
        "report_id": str(ObjectId()),
        "run_id": run.id,
        "project_id": project.id,
        "status": "generated",
        "markdown_path": str(markdown_path),
        "pdf_path": str(workspace.reports / "run_report.pdf"),
        "final_health_score": 82.0,
        "pull_request_url": None,
        "branch_name": None,
        "commit_sha": None,
        "duration_ms": 500,
        "tool_versions": {},
        "artifact_path": str(workspace.baseline / RUN_REPORT_ARTIFACT_NAME),
        "created_at": datetime.now(UTC).isoformat(),
    }
    (workspace.baseline / RUN_REPORT_ARTIFACT_NAME).write_text(
        __import__("json").dumps(artifact_payload),
        encoding="utf-8",
    )

    assert report_repository.get_by_run(run.id) is None
    response = service.get_run_report(user_id, run.id)
    assert response is not None
    assert response.final_health_score == 82.0
    assert report_repository.get_by_run(run.id) is not None
    report_agent.generate.assert_not_called()


def test_get_run_report_returns_none_when_workspace_missing(report_stack) -> None:
    (
        service,
        run_service,
        project_service,
        _workspace_manager,
        _run_repository,
        _git_operation_repository,
        report_repository,
        _event_repository,
        _report_agent,
    ) = report_stack
    user_id = str(ObjectId())
    project = project_service.create_project(user_id, ProjectCreate(name="Report Project"))
    run = run_service.create_run(user_id, RunCreate(project_id=project.id))

    assert report_repository.get_by_run(run.id) is None
    assert service.get_run_report(user_id, run.id) is None
