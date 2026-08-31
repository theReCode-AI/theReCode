"""Factory helpers for Google ADK orchestration."""

from __future__ import annotations

from app.core.config import Settings
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.run_repository import RunRepository
from app.google_adk.container import ServiceContainer
from app.google_adk.orchestrator import GoogleAdkOrchestrator
from app.services.code_fix_service import CodeFixService
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.fix_planner_service import FixPlannerService
from app.services.gemini_credential_service import GeminiCredentialService
from app.services.git_finalization_service import GitFinalizationService
from app.services.git_service import GitService
from app.services.human_approval_service import HumanApprovalService
from app.services.issue_correlation_service import IssueCorrelationService
from app.services.memory_service import MemoryService
from app.services.peer_review_service import PeerReviewService
from app.services.project_intelligence_service import ProjectIntelligenceService
from app.services.regression_test_service import RegressionTestService
from app.services.report_service import ReportService
from app.services.risk_assessment_service import RiskAssessmentService
from app.services.run_service import RunService
from app.services.self_correction_service import SelfCorrectionService
from app.services.verification_service import VerificationService


def build_service_container(
    *,
    run_repository: RunRepository,
    run_service: RunService,
    git_service: GitService,
    intelligence_service: ProjectIntelligenceService,
    diagnostic_agent_service: DiagnosticAgentService,
    issue_correlation_service: IssueCorrelationService,
    fix_planner_service: FixPlannerService,
    risk_assessment_service: RiskAssessmentService,
    code_fix_service: CodeFixService,
    verification_service: VerificationService,
    self_correction_service: SelfCorrectionService,
    regression_test_service: RegressionTestService,
    peer_review_service: PeerReviewService,
    human_approval_service: HumanApprovalService,
    memory_service: MemoryService,
    git_finalization_service: GitFinalizationService,
    report_service: ReportService,
    event_repository: AgentEventRepository,
    state_repository: AgentStateRepository,
    gemini_credential_service: GeminiCredentialService | None = None,
) -> ServiceContainer:
    return ServiceContainer(
        run_repository=run_repository,
        run_service=run_service,
        git_service=git_service,
        intelligence_service=intelligence_service,
        diagnostic_agent_service=diagnostic_agent_service,
        issue_correlation_service=issue_correlation_service,
        fix_planner_service=fix_planner_service,
        risk_assessment_service=risk_assessment_service,
        code_fix_service=code_fix_service,
        verification_service=verification_service,
        self_correction_service=self_correction_service,
        regression_test_service=regression_test_service,
        peer_review_service=peer_review_service,
        human_approval_service=human_approval_service,
        memory_service=memory_service,
        git_finalization_service=git_finalization_service,
        report_service=report_service,
        event_repository=event_repository,
        state_repository=state_repository,
        gemini_credential_service=gemini_credential_service,
    )


def build_google_adk_orchestrator(
    settings: Settings,
    services: ServiceContainer,
) -> GoogleAdkOrchestrator:
    return GoogleAdkOrchestrator(settings=settings, services=services)
