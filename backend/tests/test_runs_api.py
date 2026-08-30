from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.adk.workflows.root_orchestrator import RootOrchestrator
from app.api.dependencies import (
    get_auth_service,
    get_baseline_scan_service,
    get_code_fix_service,
    get_diagnostic_agent_service,
    get_fix_planner_service,
    get_git_finalization_service,
    get_git_service,
    get_human_approval_service,
    get_issue_correlation_service,
    get_memory_service,
    get_orchestration_service,
    get_peer_review_service,
    get_project_intelligence_service,
    get_project_service,
    get_regression_test_service,
    get_report_service,
    get_risk_assessment_service,
    get_root_orchestrator,
    get_run_service,
    get_self_correction_service,
    get_settings,
    get_user_repository,
    get_verification_service,
    get_workspace_manager,
)
from app.core.config import Settings
from app.main import create_app
from app.services.auth_service import AuthService
from app.services.baseline_scan_service import BaselineScanService
from app.services.code_fix_service import CodeFixService
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.fix_planner_service import FixPlannerService
from app.services.git_credential_service import GitCredentialService
from app.services.git_finalization_service import GitFinalizationService
from app.services.git_service import GitService
from app.services.human_approval_service import HumanApprovalService
from app.services.issue_correlation_service import IssueCorrelationService
from app.services.memory_service import MemoryService
from app.services.orchestration_service import OrchestrationService
from app.services.peer_review_service import PeerReviewService
from app.services.project_intelligence_service import ProjectIntelligenceService
from app.services.project_service import ProjectService
from app.services.regression_test_service import RegressionTestService
from app.services.report_service import ReportService
from app.services.risk_assessment_service import RiskAssessmentService
from app.services.run_service import RunService
from app.services.self_correction_service import SelfCorrectionService
from app.services.verification_service import VerificationService
from app.workspace import WorkspaceManager
from tests.scanner_mocks import build_fix_command_runner, build_mock_command_runner
from tests.test_agent_orchestration_repository import (
    InMemoryAgentEventRepository,
    InMemoryAgentStateRepository,
)
from tests.test_approval_repository import InMemoryApprovalRepository
from tests.test_auth_service import InMemoryUserRepository
from tests.test_finding_repository import InMemoryFindingRepository
from tests.test_fix_attempt_repository import InMemoryFixAttemptRepository
from tests.test_fix_plan_repository import InMemoryFixPlanRepository
from tests.test_git_operation_repository import InMemoryGitOperationRepository
from tests.test_git_service import InMemoryGitCredentialRepository
from tests.test_issue_group_repository import InMemoryIssueGroupRepository
from tests.test_memory_repository import InMemoryMemoryRepository
from tests.test_peer_review_result_repository import InMemoryPeerReviewResultRepository
from tests.test_project_intelligence_inspector import SAMPLE_FASTAPI_PROJECT
from tests.test_project_service import InMemoryLinkedRepositoryRepository, InMemoryProjectRepository
from tests.test_regression_test_result_repository import InMemoryRegressionTestResultRepository
from tests.test_report_repository import InMemoryReportRepository
from tests.test_risk_decision_repository import InMemoryRiskDecisionRepository
from tests.test_run_service import InMemoryRunRepository
from tests.test_self_correction_cycle_repository import InMemorySelfCorrectionCycleRepository
from tests.test_verification_result_repository import InMemoryVerificationResultRepository


@pytest.fixture
async def runs_client(tmp_path, mock_mongodb_lifecycle):
    user_repository = InMemoryUserRepository()
    project_repository = InMemoryProjectRepository()
    linked_repository_repository = InMemoryLinkedRepositoryRepository()
    run_repository = InMemoryRunRepository()
    event_repository = InMemoryAgentEventRepository()
    state_repository = InMemoryAgentStateRepository()
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
    workspace_manager = WorkspaceManager(tmp_path)

    settings = Settings(
        environment="test",
        jwt_secret_key="test-secret-key-with-sufficient-length",
        credentials_encryption_key="phase5-test-encryption-key-value",
    )
    auth_service = AuthService(user_repository=user_repository, app_settings=settings)
    project_service = ProjectService(project_repository, linked_repository_repository)
    run_service = RunService(run_repository, project_service, workspace_manager)
    intelligence_service = ProjectIntelligenceService(run_repository, run_service)
    baseline_scan_service = BaselineScanService(
        run_repository=run_repository,
        run_service=run_service,
        app_settings=settings,
        command_runner=build_mock_command_runner(),
    )
    diagnostic_agent_service = DiagnosticAgentService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        app_settings=settings,
        command_runner=build_mock_command_runner(),
    )
    issue_correlation_service = IssueCorrelationService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        event_repository=event_repository,
    )
    risk_assessment_service = RiskAssessmentService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        event_repository=event_repository,
    )
    code_fix_service = CodeFixService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        event_repository=event_repository,
        command_runner=build_fix_command_runner(),
    )
    verification_service = VerificationService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        event_repository=event_repository,
        command_runner=build_mock_command_runner(),
    )
    self_correction_service = SelfCorrectionService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        event_repository=event_repository,
        command_runner=build_fix_command_runner(),
        max_fix_iterations=3,
    )
    regression_test_service = RegressionTestService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        verification_result_repository=verification_result_repository,
        regression_test_result_repository=regression_test_result_repository,
        event_repository=event_repository,
        command_runner=build_mock_command_runner(),
    )
    peer_review_service = PeerReviewService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        regression_test_result_repository=regression_test_result_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        event_repository=event_repository,
    )
    human_approval_service = HumanApprovalService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        approval_repository=approval_repository,
        event_repository=event_repository,
    )
    memory_service = MemoryService(
        run_repository=run_repository,
        run_service=run_service,
        project_service=project_service,
        fix_plan_repository=fix_plan_repository,
        approval_repository=approval_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        regression_test_result_repository=regression_test_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        memory_repository=memory_repository,
        event_repository=event_repository,
    )
    fix_planner_service = FixPlannerService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        fix_plan_repository=fix_plan_repository,
        event_repository=event_repository,
        memory_service=memory_service,
    )
    git_credential_service = GitCredentialService(
        InMemoryGitCredentialRepository(),
        settings,
    )
    provider_factory = MagicMock()
    git_finalization_service = GitFinalizationService(
        run_repository=run_repository,
        run_service=run_service,
        project_service=project_service,
        git_credential_service=git_credential_service,
        provider_factory=provider_factory,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        approval_repository=approval_repository,
        git_operation_repository=git_operation_repository,
        event_repository=event_repository,
        finalization_agent=MagicMock(),
    )
    report_service = ReportService(
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
        report_agent=MagicMock(),
    )
    git_service = GitService(
        project_service=project_service,
        git_credential_service=git_credential_service,
        provider_factory=MagicMock(),
        workspace_manager=workspace_manager,
        run_service=run_service,
        app_settings=settings,
    )
    root_orchestrator = RootOrchestrator(
        run_repository=run_repository,
        run_service=run_service,
        git_service=git_service,
        intelligence_service=intelligence_service,
        diagnostic_agent_service=diagnostic_agent_service,
        event_repository=event_repository,
        state_repository=state_repository,
    )
    orchestration_service = OrchestrationService(
        run_repository=run_repository,
        orchestrator=root_orchestrator,
        event_repository=event_repository,
        state_repository=state_repository,
    )

    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_project_service] = lambda: project_service
    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_project_intelligence_service] = lambda: intelligence_service
    app.dependency_overrides[get_baseline_scan_service] = lambda: baseline_scan_service
    app.dependency_overrides[get_diagnostic_agent_service] = lambda: diagnostic_agent_service
    app.dependency_overrides[get_workspace_manager] = lambda: workspace_manager
    app.dependency_overrides[get_git_service] = lambda: git_service
    app.dependency_overrides[get_root_orchestrator] = lambda: root_orchestrator
    app.dependency_overrides[get_orchestration_service] = lambda: orchestration_service
    app.dependency_overrides[get_issue_correlation_service] = lambda: issue_correlation_service
    app.dependency_overrides[get_fix_planner_service] = lambda: fix_planner_service
    app.dependency_overrides[get_risk_assessment_service] = lambda: risk_assessment_service
    app.dependency_overrides[get_code_fix_service] = lambda: code_fix_service
    app.dependency_overrides[get_verification_service] = lambda: verification_service
    app.dependency_overrides[get_self_correction_service] = lambda: self_correction_service
    app.dependency_overrides[get_regression_test_service] = lambda: regression_test_service
    app.dependency_overrides[get_peer_review_service] = lambda: peer_review_service
    app.dependency_overrides[get_human_approval_service] = lambda: human_approval_service
    app.dependency_overrides[get_memory_service] = lambda: memory_service
    app.dependency_overrides[get_git_finalization_service] = lambda: git_finalization_service
    app.dependency_overrides[get_report_service] = lambda: report_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        async_client.fix_plan_repository = fix_plan_repository
        async_client.risk_decision_repository = risk_decision_repository
        async_client.fix_attempt_repository = fix_attempt_repository
        async_client.verification_result_repository = verification_result_repository
        async_client.self_correction_cycle_repository = self_correction_cycle_repository
        async_client.regression_test_result_repository = regression_test_result_repository
        async_client.peer_review_result_repository = peer_review_result_repository
        async_client.approval_repository = approval_repository
        async_client.memory_repository = memory_repository
        async_client.git_operation_repository = git_operation_repository
        async_client.git_finalization_service = git_finalization_service
        async_client.report_service = report_service
        async_client.report_repository = report_repository
        async_client.provider_factory = provider_factory
        yield async_client

    app.dependency_overrides.clear()


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Runs User", "password": "password123"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_run_and_get_workspace(runs_client: AsyncClient) -> None:
    headers = await _auth_headers(runs_client, "runs@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Run Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    assert run["status"] == "CREATED"

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    assert workspace.status_code == 200
    data = workspace.json()
    assert data["run_id"] == run["id"]
    assert data["repository"].endswith("/repository")
    assert data["logs"].endswith("/logs")


async def test_analyze_run_returns_project_intelligence(runs_client: AsyncClient, tmp_path) -> None:
    import shutil

    headers = await _auth_headers(runs_client, "intel@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Intel Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    analyze = await runs_client.post(f"/api/v1/runs/{run['id']}/analyze", headers=headers)
    assert analyze.status_code == 200
    data = analyze.json()
    assert data["run_id"] == run["id"]
    assert data["intelligence"]["frameworks"] == ["fastapi"]
    assert data["intelligence"]["package_manager"] == "uv"

    stored = await runs_client.get(f"/api/v1/runs/{run['id']}/intelligence", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["intelligence"]["architecture"] == "fastapi"


async def test_run_diagnostics_endpoint(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "diag@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Diagnostics Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    diagnostics = await runs_client.post(
        f"/api/v1/runs/{run['id']}/diagnostics",
        headers=headers,
        json={"tools": ["ruff", "pytest"]},
    )
    assert diagnostics.status_code == 200
    payload = diagnostics.json()
    assert payload["run_id"] == run["id"]
    assert len(payload["scans"]) == 2

    stored = await runs_client.get(f"/api/v1/runs/{run['id']}/diagnostics", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["scans"][0]["tool"] in {"ruff", "pytest"}


async def test_run_diagnostic_agents_endpoint(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "agents@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Agents Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    agents = await runs_client.post(
        f"/api/v1/runs/{run['id']}/agents",
        headers=headers,
        json={"agents": ["code_quality_agent", "test_agent"]},
    )
    assert agents.status_code == 200
    payload = agents.json()
    assert payload["run_id"] == run["id"]
    assert len(payload["agents"]) == 2

    findings = await runs_client.get(f"/api/v1/runs/{run['id']}/findings", headers=headers)
    assert findings.status_code == 200
    assert isinstance(findings.json(), list)


async def test_execute_run_orchestration_endpoint(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "orchestrate@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Orchestration Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    execute = await runs_client.post(
        f"/api/v1/runs/{run['id']}/execute",
        headers=headers,
        json={
            "skip_clone": True,
            "agents": ["code_quality_agent", "test_agent"],
        },
    )
    assert execute.status_code == 200
    payload = execute.json()
    assert payload["run_id"] == run["id"]
    assert payload["state"]["status"] == "completed"
    assert payload["event_count"] > 0

    events = await runs_client.get(f"/api/v1/runs/{run['id']}/events", headers=headers)
    assert events.status_code == 200
    assert len(events.json()) == payload["event_count"]

    state = await runs_client.get(f"/api/v1/runs/{run['id']}/state", headers=headers)
    assert state.status_code == 200
    assert state.json()["status"] == "completed"


async def test_correlate_run_findings_endpoint(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "correlate@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Correlate Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    agents = await runs_client.post(
        f"/api/v1/runs/{run['id']}/agents",
        headers=headers,
        json={"agents": ["code_quality_agent", "test_agent"]},
    )
    assert agents.status_code == 200

    correlate = await runs_client.post(f"/api/v1/runs/{run['id']}/correlate", headers=headers)
    assert correlate.status_code == 200
    payload = correlate.json()
    assert payload["run_id"] == run["id"]
    assert payload["issue_group_count"] >= 0

    issues = await runs_client.get(f"/api/v1/runs/{run['id']}/issues", headers=headers)
    assert issues.status_code == 200
    assert len(issues.json()) == payload["issue_group_count"]


async def test_plan_run_fixes_endpoint(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "plan@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Plan Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    await runs_client.post(
        f"/api/v1/runs/{run['id']}/agents",
        headers=headers,
        json={"agents": ["code_quality_agent", "test_agent"]},
    )
    await runs_client.post(f"/api/v1/runs/{run['id']}/correlate", headers=headers)

    plan = await runs_client.post(f"/api/v1/runs/{run['id']}/plan", headers=headers)
    assert plan.status_code == 200
    payload = plan.json()
    assert payload["run_id"] == run["id"]
    assert payload["patch_plan_count"] >= 0

    plans = await runs_client.get(f"/api/v1/runs/{run['id']}/plans", headers=headers)
    assert plans.status_code == 200
    assert len(plans.json()) == payload["patch_plan_count"]

    if payload["patch_plan_count"]:
        plan_id = plans.json()[0]["patch_plan_id"]
        detail = await runs_client.get(
            f"/api/v1/runs/{run['id']}/plans/{plan_id}",
            headers=headers,
        )
        assert detail.status_code == 200
        assert detail.json()["patch_plan_id"] == plan_id
        assert detail.json()["rollback_strategy"]


async def test_assess_run_risk_endpoint(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "risk@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Risk Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = workspace.json()["repository"]
    shutil.copytree(SAMPLE_FASTAPI_PROJECT, repository_path, dirs_exist_ok=True)

    await runs_client.post(f"/api/v1/runs/{run['id']}/correlate", headers=headers)

    now = datetime.now(UTC)
    patch_plan = PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Auth security issue",
        root_cause="Unsafe auth handling",
        affected_files=["src/auth/login.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth/login.py",
                description="Harden auth flow",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest"],
        estimated_risk=RiskLevel.HIGH,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Security fix",
        rollback_strategy="Restore auth module",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])
    workspace_response = await runs_client.get(
        f"/api/v1/runs/{run['id']}/workspace",
        headers=headers,
    )
    workspace_data = workspace_response.json()
    from pathlib import Path

    from app.services.fix_planner_service import FIX_PLANS_ARTIFACT_NAME

    baseline = Path(workspace_data["baseline"])
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / FIX_PLANS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    assess = await runs_client.post(f"/api/v1/runs/{run['id']}/assess-risk", headers=headers)
    assert assess.status_code == 200
    payload = assess.json()
    assert payload["run_id"] == run["id"]
    assert payload["decision_count"] == 1
    assert payload["approval_required_count"] == 1
    assert payload["run_status"] == "AWAITING_APPROVAL"

    decisions = await runs_client.get(f"/api/v1/runs/{run['id']}/risk-decisions", headers=headers)
    assert decisions.status_code == 200
    assert len(decisions.json()) == 1

    decision_id = decisions.json()[0]["risk_decision_id"]
    detail = await runs_client.get(
        f"/api/v1/runs/{run['id']}/risk-decisions/{decision_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["approval_required"] is True

    prepare = await runs_client.post(
        f"/api/v1/runs/{run['id']}/approvals/prepare",
        headers=headers,
    )
    assert prepare.status_code == 200
    assert prepare.json()["pending_count"] == 1

    approval_id = prepare.json()["approvals"][0]["approval_id"]
    decide = await runs_client.post(
        f"/api/v1/runs/{run['id']}/approvals/{approval_id}/decide",
        headers=headers,
        json={"decision": "approve"},
    )
    assert decide.status_code == 200
    assert decide.json()["run_status"] == "FIXING"
    assert decide.json()["approval"]["status"] == "approved"


async def test_apply_run_fixes_applies_autonomous_plan(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime
    from pathlib import Path

    from bson import ObjectId

    from app.adk.risk.policy_engine import RiskPolicyEngine
    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
    from app.services.risk_assessment_service import RISK_DECISIONS_ARTIFACT_NAME

    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "fix@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Fix Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = Path(workspace.json()["repository"])
    target = repository_path / "src" / "utils.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unused_var = 1\n", encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan = PatchPlan(
        patch_plan_id=str(ObjectId()),
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused variable",
        affected_files=["src/utils.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/utils.py",
                description="Remove unused variable",
                change_type=ChangeType.LINT_FIX.value,
            ),
        ],
        expected_tests=["uv run ruff check src/utils.py"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run["id"], [patch_plan])
    runs_client.risk_decision_repository.replace_for_run(run["id"], risk_decisions)

    baseline = Path(workspace.json()["baseline"])
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / RISK_DECISIONS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    fix = await runs_client.post(f"/api/v1/runs/{run['id']}/fix", headers=headers)
    assert fix.status_code == 200
    payload = fix.json()
    assert payload["applied_count"] == 1
    assert payload["run_status"] == "FIXING"

    attempts = await runs_client.get(f"/api/v1/runs/{run['id']}/fix-attempts", headers=headers)
    assert attempts.status_code == 200
    assert len(attempts.json()) == 1
    assert attempts.json()[0]["status"] == "applied"

    attempt_id = attempts.json()[0]["fix_attempt_id"]
    detail = await runs_client.get(
        f"/api/v1/runs/{run['id']}/fix-attempts/{attempt_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["changed_files"] == ["src/utils.py"]


async def test_apply_run_fixes_requires_risk_decisions(runs_client: AsyncClient) -> None:
    headers = await _auth_headers(runs_client, "fix-required@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Fix Required Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    fix = await runs_client.post(f"/api/v1/runs/{run['id']}/fix", headers=headers)
    assert fix.status_code == 400
    assert "Risk decisions" in fix.json()["detail"]


async def test_verify_run_fixes_applied_attempt(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime
    from pathlib import Path

    from bson import ObjectId

    from app.adk.risk.policy_engine import RiskPolicyEngine
    from app.models.fix_attempt import FixAttempt
    from app.models.fix_attempt_enums import FixAttemptStatus
    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
    from app.services.code_fix_service import FIX_ATTEMPTS_ARTIFACT_NAME
    from app.services.risk_assessment_service import RISK_DECISIONS_ARTIFACT_NAME

    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "verify@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Verify Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    repository_path = Path(workspace.json()["repository"])
    working_path = Path(workspace.json()["working"])
    target = repository_path / "src" / "utils.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unused_var = 1\n", encoding="utf-8")
    working_target = working_path / "src" / "utils.py"
    working_target.parent.mkdir(parents=True, exist_ok=True)
    working_target.write_text("fixed_var = 1\n", encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused variable",
        affected_files=["src/utils.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/utils.py",
                description="Remove unused variable",
                change_type=ChangeType.LINT_FIX.value,
            ),
        ],
        expected_tests=["uv run ruff check src/utils.py"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run["id"], [patch_plan])
    runs_client.risk_decision_repository.replace_for_run(run["id"], risk_decisions)

    fix_attempt = FixAttempt(
        fix_attempt_id=fix_attempt_id,
        run_id=run["id"],
        patch_plan_id=patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/utils.py"],
        changed_files=["src/utils.py"],
        created_at=now,
    )
    runs_client.fix_attempt_repository.add(fix_attempt)

    baseline = Path(workspace.json()["baseline"])
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / RISK_DECISIONS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")
    (baseline / FIX_ATTEMPTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    verify = await runs_client.post(f"/api/v1/runs/{run['id']}/verify", headers=headers)
    assert verify.status_code == 200
    payload = verify.json()
    assert payload["passed_count"] == 1
    assert payload["run_status"] == "VERIFYING"

    results = await runs_client.get(
        f"/api/v1/runs/{run['id']}/verification-results",
        headers=headers,
    )
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert results.json()[0]["status"] == "passed"

    result_id = results.json()[0]["verification_result_id"]
    detail = await runs_client.get(
        f"/api/v1/runs/{run['id']}/verification-results/{result_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["passed_checks"] >= 1


async def test_verify_run_requires_fix_attempts(runs_client: AsyncClient) -> None:
    headers = await _auth_headers(runs_client, "verify-required@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Verify Required Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    verify = await runs_client.post(f"/api/v1/runs/{run['id']}/verify", headers=headers)
    assert verify.status_code == 400
    assert "Fix attempts" in verify.json()["detail"]


async def test_self_correct_run_retries_failed_verification(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime
    from pathlib import Path

    from bson import ObjectId

    from app.adk.risk.policy_engine import RiskPolicyEngine
    from app.models.fix_attempt import FixAttempt
    from app.models.fix_attempt_enums import FixAttemptStatus
    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
    from app.models.verification_enums import (
        VerificationCheckStatus,
        VerificationCheckType,
        VerificationStatus,
    )
    from app.models.verification_result import VerificationCheck, VerificationResult

    monkeypatch.setattr("app.adk.fixing.applicator.is_tool_available", lambda _: True)
    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "self-correct@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Self Correct Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    working_path = Path(workspace.json()["working"])
    target = working_path / "src" / "utils.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("unused_var = 1\n", encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused variable",
        affected_files=["src/utils.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/utils.py",
                description="Remove unused variable",
                change_type=ChangeType.LINT_FIX.value,
            ),
        ],
        expected_tests=["uv run ruff check src/utils.py"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])
    risk_decisions = RiskPolicyEngine().assess(run["id"], [patch_plan])
    runs_client.risk_decision_repository.replace_for_run(run["id"], risk_decisions)

    backup_path = Path(workspace.json()["patches"]) / patch_plan_id / "pre-patch"
    backup_path.mkdir(parents=True, exist_ok=True)
    backup_file = backup_path / "src" / "utils.py"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    backup_file.write_text("unused_var = 1\n", encoding="utf-8")

    runs_client.fix_attempt_repository.add(
        FixAttempt(
            fix_attempt_id=fix_attempt_id,
            run_id=run["id"],
            patch_plan_id=patch_plan_id,
            attempt_number=1,
            status=FixAttemptStatus.APPLIED,
            planned_files=["src/utils.py"],
            changed_files=["src/utils.py"],
            backup_path=str(backup_path),
            created_at=now,
        ),
    )
    runs_client.verification_result_repository.add(
        VerificationResult(
            verification_result_id=str(ObjectId()),
            run_id=run["id"],
            fix_attempt_id=fix_attempt_id,
            patch_plan_id=patch_plan_id,
            status=VerificationStatus.FAILED,
            checks=[
                VerificationCheck(
                    check_type=VerificationCheckType.COMMAND,
                    name="uv run ruff check src/utils.py",
                    status=VerificationCheckStatus.FAILED,
                    exit_code=1,
                    message="lint still failing",
                ),
            ],
            passed_checks=0,
            failed_checks=1,
            failure_summary="lint still failing",
            created_at=now,
        ),
    )

    correct = await runs_client.post(f"/api/v1/runs/{run['id']}/self-correct", headers=headers)
    assert correct.status_code == 200
    payload = correct.json()
    assert payload["passed_count"] == 1
    assert payload["run_status"] == "VERIFYING"

    cycles = await runs_client.get(
        f"/api/v1/runs/{run['id']}/self-correction-cycles",
        headers=headers,
    )
    assert cycles.status_code == 200
    assert len(cycles.json()) == 1
    assert cycles.json()[0]["status"] == "passed"
    assert cycles.json()[0]["rollback_applied"] is True


async def test_self_correct_run_requires_failed_verification(runs_client: AsyncClient) -> None:
    headers = await _auth_headers(runs_client, "self-correct-required@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Self Correct Required"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    correct = await runs_client.post(f"/api/v1/runs/{run['id']}/self-correct", headers=headers)
    assert correct.status_code == 400
    assert "Failed verification" in correct.json()["detail"]


async def test_run_regression_tests_skips_lint_only_verified_fix(
    runs_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime
    from pathlib import Path

    from bson import ObjectId

    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
    from app.models.verification_enums import VerificationStatus
    from app.models.verification_result import VerificationResult
    from app.services.verification_service import VERIFICATION_RESULTS_ARTIFACT_NAME

    monkeypatch.setattr("app.scanners.base.is_tool_available", lambda _: True)
    headers = await _auth_headers(runs_client, "regression@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Regression Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    working_path = Path(workspace.json()["working"])
    target = working_path / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Lint issue",
        root_cause="Unused variable",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Remove unused variable",
                change_type=ChangeType.LINT_FIX.value,
            ),
        ],
        expected_tests=["uv run ruff check src/auth.py"],
        estimated_risk=RiskLevel.LOW,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Safe lint fix",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])

    verification_result = VerificationResult(
        verification_result_id=str(ObjectId()),
        run_id=run["id"],
        fix_attempt_id=fix_attempt_id,
        patch_plan_id=patch_plan_id,
        status=VerificationStatus.PASSED,
        created_at=now,
    )
    runs_client.verification_result_repository.add(verification_result)

    baseline = Path(workspace.json()["baseline"])
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / VERIFICATION_RESULTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    regression = await runs_client.post(
        f"/api/v1/runs/{run['id']}/regression-tests",
        headers=headers,
    )
    assert regression.status_code == 200
    payload = regression.json()
    assert payload["result_count"] == 1
    assert payload["skipped_count"] == 1
    assert payload["run_status"] == "VERIFYING"

    results = await runs_client.get(
        f"/api/v1/runs/{run['id']}/regression-tests",
        headers=headers,
    )
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert results.json()[0]["status"] == "skipped"

    result_id = results.json()[0]["regression_test_id"]
    detail = await runs_client.get(
        f"/api/v1/runs/{run['id']}/regression-tests/{result_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["regression_test_id"] == result_id


async def test_run_regression_tests_requires_passed_verifications(runs_client: AsyncClient) -> None:
    headers = await _auth_headers(runs_client, "regression-required@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Regression Required"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    regression = await runs_client.post(
        f"/api/v1/runs/{run['id']}/regression-tests",
        headers=headers,
    )
    assert regression.status_code == 400
    assert "Passed verification" in regression.json()["detail"]


async def test_peer_review_run_approves_regression_passed_fix(runs_client: AsyncClient) -> None:
    from datetime import UTC, datetime
    from pathlib import Path

    from bson import ObjectId

    from app.models.fix_attempt import FixAttempt
    from app.models.fix_attempt_enums import FixAttemptStatus
    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
    from app.models.regression_test_enums import RegressionTestStatus
    from app.models.regression_test_result import RegressionTestResult
    from app.models.verification_enums import VerificationStatus
    from app.models.verification_result import VerificationResult
    from app.services.regression_test_service import REGRESSION_TEST_RESULTS_ARTIFACT_NAME

    headers = await _auth_headers(runs_client, "peer-review@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Peer Review Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    working_path = Path(workspace.json()["working"])
    target = working_path / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")

    diff_path = Path(workspace.json()["patches"]) / "plan" / "changes.diff"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(
        "--- a/src/auth.py\n+++ b/src/auth.py\n@@\n-TOKEN = eval('1')\n+TOKEN = 'safe'\n",
        encoding="utf-8",
    )

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    verification_result_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Security issue",
        root_cause="Unsafe eval usage",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Remove eval",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest tests/test_auth.py"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval with safe parser",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])

    fix_attempt = FixAttempt(
        fix_attempt_id=fix_attempt_id,
        run_id=run["id"],
        patch_plan_id=patch_plan_id,
        attempt_number=1,
        status=FixAttemptStatus.APPLIED,
        planned_files=["src/auth.py"],
        changed_files=["src/auth.py"],
        diff_artifact_path=str(diff_path),
        created_at=now,
    )
    runs_client.fix_attempt_repository.add(fix_attempt)

    verification = VerificationResult(
        verification_result_id=verification_result_id,
        run_id=run["id"],
        fix_attempt_id=fix_attempt_id,
        patch_plan_id=patch_plan_id,
        status=VerificationStatus.PASSED,
        created_at=now,
    )
    runs_client.verification_result_repository.add(verification)

    regression = RegressionTestResult(
        regression_test_id=str(ObjectId()),
        run_id=run["id"],
        patch_plan_id=patch_plan_id,
        fix_attempt_id=fix_attempt_id,
        verification_result_id=verification_result_id,
        status=RegressionTestStatus.PASSED,
        eligible=True,
        test_file_path="tests/regression/test_regression_example.py",
        targeted_passed=1,
        suite_passed=1,
        created_at=now,
    )
    runs_client.regression_test_result_repository.add(regression)

    baseline = Path(workspace.json()["baseline"])
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / REGRESSION_TEST_RESULTS_ARTIFACT_NAME).write_text("[]", encoding="utf-8")

    review = await runs_client.post(f"/api/v1/runs/{run['id']}/peer-review", headers=headers)
    assert review.status_code == 200
    payload = review.json()
    assert payload["result_count"] == 1
    assert payload["approved_count"] == 1
    assert payload["run_status"] == "FINAL_REVIEW"

    results = await runs_client.get(f"/api/v1/runs/{run['id']}/peer-reviews", headers=headers)
    assert results.status_code == 200
    assert len(results.json()) == 1
    assert results.json()[0]["verdict"] == "approved"
    assert len(results.json()[0]["reviewer_opinions"]) == 3

    review_id = results.json()[0]["peer_review_id"]
    detail = await runs_client.get(
        f"/api/v1/runs/{run['id']}/peer-reviews/{review_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["peer_review_id"] == review_id


async def test_peer_review_run_requires_regression_results(runs_client: AsyncClient) -> None:
    headers = await _auth_headers(runs_client, "peer-review-required@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Peer Review Required"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    review = await runs_client.post(f"/api/v1/runs/{run['id']}/peer-review", headers=headers)
    assert review.status_code == 400
    assert "Regression test" in review.json()["detail"]


async def test_capture_run_memory_and_list_project_memories(runs_client: AsyncClient) -> None:
    import shutil
    from datetime import UTC, datetime

    from bson import ObjectId

    from app.models.approval import HumanApproval
    from app.models.approval_enums import ApprovalStatus, ApprovalTrigger, HumanDecision

    headers = await _auth_headers(runs_client, "memory@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Memory Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    shutil.copytree(
        SAMPLE_FASTAPI_PROJECT,
        workspace.json()["repository"],
        dirs_exist_ok=True,
    )
    analyze = await runs_client.post(f"/api/v1/runs/{run['id']}/analyze", headers=headers)
    assert analyze.status_code == 200

    now = datetime.now(UTC)
    runs_client.approval_repository.add(
        HumanApproval(
            approval_id=str(ObjectId()),
            run_id=run["id"],
            patch_plan_id=str(ObjectId()),
            trigger=ApprovalTrigger.RISK_GATE,
            status=ApprovalStatus.APPROVED,
            reason="High risk patch",
            human_decision=HumanDecision.APPROVE,
            human_feedback="Approved after review",
            created_at=now,
        ),
    )

    capture = await runs_client.post(
        f"/api/v1/runs/{run['id']}/memory/capture",
        headers=headers,
    )
    assert capture.status_code == 200
    payload = capture.json()
    assert payload["memory_count"] >= 2
    assert payload["project_memory_count"] >= 1
    assert payload["decision_memory_count"] >= 1

    memories = await runs_client.get(
        f"/api/v1/projects/{project['id']}/memories",
        headers=headers,
    )
    assert memories.status_code == 200
    assert len(memories.json()) == payload["memory_count"]

    memory_id = memories.json()[0]["memory_id"]
    detail = await runs_client.get(
        f"/api/v1/projects/{project['id']}/memories/{memory_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["memory_id"] == memory_id


async def test_finalize_run_git_and_list_operations(runs_client: AsyncClient) -> None:
    from datetime import UTC, datetime
    from pathlib import Path
    from unittest.mock import MagicMock

    from bson import ObjectId

    from app.adk.git_finalization.engine import GitFinalizationResult
    from app.git.types import RepositoryValidationResult
    from app.models.fix_attempt import FixAttempt
    from app.models.fix_attempt_enums import FixAttemptStatus
    from app.models.git_operation_enums import GitOperationStatus
    from app.models.patch_plan import ExpectedModification, PatchPlan
    from app.models.patch_plan_enums import ChangeType, FixScope, PatchPlanStatus, RiskLevel
    from app.models.peer_review_enums import PeerReviewVerdict
    from app.models.peer_review_result import PeerReviewResult
    from app.models.run import RunStatus
    from app.models.verification_enums import VerificationStatus
    from app.models.verification_result import VerificationResult
    from app.schemas.git import GitCredentialCreate

    headers = await _auth_headers(runs_client, "git-finalize@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Git Finalize Project"},
        )
    ).json()

    repository = (
        await runs_client.post(
            f"/api/v1/projects/{project['id']}/repositories",
            headers=headers,
            json={"provider": "github", "full_name": "org/repo"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"], "repository_id": repository["id"]},
        )
    ).json()

    run_repo = runs_client.git_finalization_service._run_repository
    user_id = str(next(iter(run_repo._runs.values()))["user_id"])

    runs_client.git_finalization_service._git_credential_service.save_credential(
        user_id,
        GitCredentialCreate(provider="github", access_token="ghp_secret"),
    )

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    git_dir = Path(workspace.json()["repository"]) / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    target = Path(workspace.json()["working"]) / "src" / "auth.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("TOKEN = 'safe'\n", encoding="utf-8")

    now = datetime.now(UTC)
    patch_plan_id = str(ObjectId())
    fix_attempt_id = str(ObjectId())
    verification_result_id = str(ObjectId())
    patch_plan = PatchPlan(
        patch_plan_id=patch_plan_id,
        run_id=run["id"],
        issue_group_id=str(ObjectId()),
        title="Security issue",
        root_cause="Unsafe eval usage",
        affected_files=["src/auth.py"],
        expected_modifications=[
            ExpectedModification(
                file="src/auth.py",
                description="Remove eval",
                change_type=ChangeType.SECURITY_REMEDIATION.value,
            ),
        ],
        expected_tests=["uv run pytest"],
        estimated_risk=RiskLevel.MEDIUM,
        expected_scope=FixScope.SINGLE_FILE,
        solution_rationale="Replace eval",
        rollback_strategy="Revert file",
        priority_rank=1,
        status=PatchPlanStatus.READY,
        created_at=now,
    )
    runs_client.fix_plan_repository.replace_for_run(run["id"], [patch_plan])
    runs_client.fix_attempt_repository.add(
        FixAttempt(
            fix_attempt_id=fix_attempt_id,
            run_id=run["id"],
            patch_plan_id=patch_plan_id,
            attempt_number=1,
            status=FixAttemptStatus.APPLIED,
            planned_files=["src/auth.py"],
            changed_files=["src/auth.py"],
            created_at=now,
        ),
    )
    runs_client.verification_result_repository.add(
        VerificationResult(
            verification_result_id=verification_result_id,
            run_id=run["id"],
            fix_attempt_id=fix_attempt_id,
            patch_plan_id=patch_plan_id,
            status=VerificationStatus.PASSED,
            created_at=now,
        ),
    )
    runs_client.peer_review_result_repository.add(
        PeerReviewResult(
            peer_review_id=str(ObjectId()),
            run_id=run["id"],
            patch_plan_id=patch_plan_id,
            fix_attempt_id=fix_attempt_id,
            verification_result_id=verification_result_id,
            regression_test_id=str(ObjectId()),
            verdict=PeerReviewVerdict.APPROVED,
            synthesis_summary="Approved",
            reviewer_opinions=[],
            created_at=now,
        ),
    )
    run_repo.update_status(run["id"], user_id, RunStatus.FINAL_REVIEW)

    mock_provider = MagicMock()
    mock_provider.validate_repository.return_value = RepositoryValidationResult(
        valid=True,
        provider="github",
        full_name="org/repo",
        default_branch="main",
        clone_url="https://github.com/org/repo.git",
    )
    runs_client.provider_factory.get_provider.return_value = mock_provider
    runs_client.git_finalization_service._finalization_agent.finalize.return_value = (
        GitFinalizationResult(
            status=GitOperationStatus.PR_CREATED,
            branch_name="agent/run-security",
            base_branch="main",
            commit_sha="abc123",
            push_commit_sha="abc123",
            pull_request_url="https://github.com/org/repo/pull/1",
            pull_request_number=1,
            title="theReCode: Security issue",
            description="PR body",
        )
    )

    finalize = await runs_client.post(
        f"/api/v1/runs/{run['id']}/git/finalize",
        headers=headers,
    )
    assert finalize.status_code == 200
    payload = finalize.json()
    assert payload["operation"]["status"] == "pr_created"
    assert payload["operation"]["pull_request_url"] == "https://github.com/org/repo/pull/1"

    operations = await runs_client.get(
        f"/api/v1/runs/{run['id']}/git/operations",
        headers=headers,
    )
    assert operations.status_code == 200
    assert len(operations.json()) == 1


async def test_generate_run_report_and_get_report(runs_client: AsyncClient) -> None:
    from datetime import UTC, datetime
    from pathlib import Path
    from unittest.mock import MagicMock

    from bson import ObjectId

    from app.models.git_operation import GitOperation
    from app.models.git_operation_enums import GitOperationStatus
    from app.models.run import RunStatus

    headers = await _auth_headers(runs_client, "report@example.com")

    project = (
        await runs_client.post(
            "/api/v1/projects",
            headers=headers,
            json={"name": "Report Project"},
        )
    ).json()

    run = (
        await runs_client.post(
            "/api/v1/runs",
            headers=headers,
            json={"project_id": project["id"]},
        )
    ).json()

    run_repo = runs_client.report_service._run_repository
    user_id = str(next(iter(run_repo._runs.values()))["user_id"])
    run_repo.update_status(run["id"], user_id, RunStatus.REPORTING)

    now = datetime.now(UTC)
    runs_client.git_operation_repository.add(
        GitOperation(
            git_operation_id=str(ObjectId()),
            run_id=run["id"],
            project_id=project["id"],
            repository_id=str(ObjectId()),
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

    workspace = await runs_client.get(f"/api/v1/runs/{run['id']}/workspace", headers=headers)
    markdown_path = Path(workspace.json()["reports"]) / "run_report.md"
    pdf_path = Path(workspace.json()["reports"]) / "run_report.pdf"
    generated = MagicMock()
    generated.markdown = "# Report"
    generated.plain_text_lines = ["Report"]
    generated.final_health_score = 88.0
    generated.pull_request_url = "https://github.com/org/repo/pull/1"
    generated.branch_name = "agent/run-security"
    generated.commit_sha = "abc123"
    generated.duration_ms = 1000
    generated.tool_versions = {"ruff": "0.8.0"}
    runs_client.report_service._report_agent.generate.return_value = (
        generated,
        MagicMock(markdown_path=markdown_path, pdf_path=pdf_path),
    )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# Report", encoding="utf-8")
    pdf_path.write_bytes(b"%PDF-1.4 test")

    generate = await runs_client.post(
        f"/api/v1/runs/{run['id']}/reports/generate",
        headers=headers,
    )
    assert generate.status_code == 200
    assert generate.json()["run_status"] == RunStatus.COMPLETED.value

    report = await runs_client.get(f"/api/v1/runs/{run['id']}/reports", headers=headers)
    assert report.status_code == 200
    assert report.json()["final_health_score"] == 88.0

    markdown = await runs_client.get(
        f"/api/v1/runs/{run['id']}/reports/markdown",
        headers=headers,
    )
    assert markdown.status_code == 200
    assert markdown.json()["markdown"] == "# Report"
