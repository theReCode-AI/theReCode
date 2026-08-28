"""Service container passed into Google ADK workflow execution."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.run_repository import RunRepository
from app.services.code_fix_service import CodeFixService
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.fix_planner_service import FixPlannerService
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


@dataclass(frozen=True)
class ServiceContainer:
    run_repository: RunRepository
    run_service: RunService
    git_service: GitService
    intelligence_service: ProjectIntelligenceService
    diagnostic_agent_service: DiagnosticAgentService
    issue_correlation_service: IssueCorrelationService
    fix_planner_service: FixPlannerService
    risk_assessment_service: RiskAssessmentService
    code_fix_service: CodeFixService
    verification_service: VerificationService
    self_correction_service: SelfCorrectionService
    regression_test_service: RegressionTestService
    peer_review_service: PeerReviewService
    human_approval_service: HumanApprovalService
    memory_service: MemoryService
    git_finalization_service: GitFinalizationService
    report_service: ReportService
    event_repository: AgentEventRepository
    state_repository: AgentStateRepository


_service_container: ContextVar[ServiceContainer | None] = ContextVar(
    "codethera_service_container",
    default=None,
)


def set_service_container(container: ServiceContainer) -> None:
    _service_container.set(container)


def get_service_container() -> ServiceContainer:
    container = _service_container.get()
    if container is None:
        raise RuntimeError("Service container is not set for this ADK workflow run.")
    return container


def clear_service_container() -> None:
    _service_container.set(None)
