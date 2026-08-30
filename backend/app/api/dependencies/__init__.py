from fastapi import Depends
from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.db.dependencies import get_database
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.agent_state_repository import AgentStateRepository
from app.db.repositories.approval_repository import ApprovalRepository
from app.db.repositories.chat_message_repository import ChatMessageRepository
from app.db.repositories.finding_repository import FindingRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.git_credential_repository import GitCredentialRepository
from app.db.repositories.git_operation_repository import GitOperationRepository
from app.db.repositories.issue_group_repository import IssueGroupRepository
from app.db.repositories.linked_repository_repository import LinkedRepositoryRepository
from app.db.repositories.memory_repository import MemoryRepository
from app.db.repositories.peer_review_result_repository import PeerReviewResultRepository
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.regression_test_result_repository import RegressionTestResultRepository
from app.db.repositories.report_repository import ReportRepository
from app.db.repositories.risk_decision_repository import RiskDecisionRepository
from app.db.repositories.run_repository import RunRepository
from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.git import GitProviderFactory
from app.google_adk.factory import build_google_adk_orchestrator, build_service_container
from app.google_adk.orchestrator import GoogleAdkOrchestrator
from app.services.auth_service import AuthService
from app.services.baseline_scan_service import BaselineScanService
from app.services.chat_service import ChatService
from app.services.code_fix_service import CodeFixService
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.fix_planner_service import FixPlannerService
from app.services.gemini_chat_client import GeminiChatClient
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
from app.services.run_progress_stream_service import RunProgressStreamService
from app.services.run_service import RunService
from app.services.self_correction_service import SelfCorrectionService
from app.services.verification_service import VerificationService
from app.workspace import WorkspaceManager


def get_user_repository(database: Database = Depends(get_database)) -> UserRepository:
    return UserRepository(database)


def get_project_repository(database: Database = Depends(get_database)) -> ProjectRepository:
    return ProjectRepository(database)


def get_linked_repository_repository(
    database: Database = Depends(get_database),
) -> LinkedRepositoryRepository:
    return LinkedRepositoryRepository(database)


def get_git_credential_repository(
    database: Database = Depends(get_database),
) -> GitCredentialRepository:
    return GitCredentialRepository(database)


def get_finding_repository(database: Database = Depends(get_database)) -> FindingRepository:
    return FindingRepository(database)


def get_agent_event_repository(database: Database = Depends(get_database)) -> AgentEventRepository:
    return AgentEventRepository(database)


def get_agent_state_repository(database: Database = Depends(get_database)) -> AgentStateRepository:
    return AgentStateRepository(database)


def get_fix_plan_repository(database: Database = Depends(get_database)) -> FixPlanRepository:
    return FixPlanRepository(database)


def get_issue_group_repository(
    database: Database = Depends(get_database),
) -> IssueGroupRepository:
    return IssueGroupRepository(database)


def get_risk_decision_repository(
    database: Database = Depends(get_database),
) -> RiskDecisionRepository:
    return RiskDecisionRepository(database)


def get_fix_attempt_repository(
    database: Database = Depends(get_database),
) -> FixAttemptRepository:
    return FixAttemptRepository(database)


def get_verification_result_repository(
    database: Database = Depends(get_database),
) -> VerificationResultRepository:
    return VerificationResultRepository(database)


def get_self_correction_cycle_repository(
    database: Database = Depends(get_database),
) -> SelfCorrectionCycleRepository:
    return SelfCorrectionCycleRepository(database)


def get_regression_test_result_repository(
    database: Database = Depends(get_database),
) -> RegressionTestResultRepository:
    return RegressionTestResultRepository(database)


def get_peer_review_result_repository(
    database: Database = Depends(get_database),
) -> PeerReviewResultRepository:
    return PeerReviewResultRepository(database)


def get_approval_repository(
    database: Database = Depends(get_database),
) -> ApprovalRepository:
    return ApprovalRepository(database)


def get_memory_repository(
    database: Database = Depends(get_database),
) -> MemoryRepository:
    return MemoryRepository(database)


def get_git_operation_repository(
    database: Database = Depends(get_database),
) -> GitOperationRepository:
    return GitOperationRepository(database)


def get_report_repository(
    database: Database = Depends(get_database),
) -> ReportRepository:
    return ReportRepository(database)


def get_chat_message_repository(
    database: Database = Depends(get_database),
) -> ChatMessageRepository:
    return ChatMessageRepository(database)


def get_run_repository(database: Database = Depends(get_database)) -> RunRepository:
    return RunRepository(database)


def get_workspace_manager(
    app_settings: Settings = Depends(get_settings),
) -> WorkspaceManager:
    return WorkspaceManager(app_settings.resolved_workspace_root)


def get_git_provider_factory(
    app_settings: Settings = Depends(get_settings),
) -> GitProviderFactory:
    return GitProviderFactory(
        github_api_base_url=app_settings.github_api_base_url,
        gitlab_api_base_url=app_settings.gitlab_api_base_url,
    )


def get_auth_service(
    user_repository: UserRepository = Depends(get_user_repository),
    app_settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(user_repository=user_repository, app_settings=app_settings)


def get_project_service(
    project_repository: ProjectRepository = Depends(get_project_repository),
    linked_repository_repository: LinkedRepositoryRepository = Depends(
        get_linked_repository_repository,
    ),
) -> ProjectService:
    return ProjectService(
        project_repository=project_repository,
        linked_repository_repository=linked_repository_repository,
    )


def get_git_credential_service(
    credential_repository: GitCredentialRepository = Depends(get_git_credential_repository),
    app_settings: Settings = Depends(get_settings),
) -> GitCredentialService:
    return GitCredentialService(
        credential_repository=credential_repository,
        app_settings=app_settings,
    )


def get_run_service(
    run_repository: RunRepository = Depends(get_run_repository),
    project_service: ProjectService = Depends(get_project_service),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
) -> RunService:
    return RunService(
        run_repository=run_repository,
        project_service=project_service,
        workspace_manager=workspace_manager,
    )


def get_project_intelligence_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
) -> ProjectIntelligenceService:
    return ProjectIntelligenceService(
        run_repository=run_repository,
        run_service=run_service,
    )


def get_baseline_scan_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    app_settings: Settings = Depends(get_settings),
) -> BaselineScanService:
    return BaselineScanService(
        run_repository=run_repository,
        run_service=run_service,
        app_settings=app_settings,
    )


def get_diagnostic_agent_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    finding_repository: FindingRepository = Depends(get_finding_repository),
    app_settings: Settings = Depends(get_settings),
) -> DiagnosticAgentService:
    return DiagnosticAgentService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        app_settings=app_settings,
    )


def get_issue_correlation_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    finding_repository: FindingRepository = Depends(get_finding_repository),
    issue_group_repository: IssueGroupRepository = Depends(get_issue_group_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> IssueCorrelationService:
    return IssueCorrelationService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        event_repository=event_repository,
    )


def get_memory_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    project_service: ProjectService = Depends(get_project_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    approval_repository: ApprovalRepository = Depends(get_approval_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    regression_test_result_repository: RegressionTestResultRepository = Depends(
        get_regression_test_result_repository,
    ),
    peer_review_result_repository: PeerReviewResultRepository = Depends(
        get_peer_review_result_repository,
    ),
    self_correction_cycle_repository: SelfCorrectionCycleRepository = Depends(
        get_self_correction_cycle_repository,
    ),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> MemoryService:
    return MemoryService(
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


def get_git_finalization_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    project_service: ProjectService = Depends(get_project_service),
    git_credential_service: GitCredentialService = Depends(get_git_credential_service),
    provider_factory: GitProviderFactory = Depends(get_git_provider_factory),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    peer_review_result_repository: PeerReviewResultRepository = Depends(
        get_peer_review_result_repository,
    ),
    self_correction_cycle_repository: SelfCorrectionCycleRepository = Depends(
        get_self_correction_cycle_repository,
    ),
    approval_repository: ApprovalRepository = Depends(get_approval_repository),
    git_operation_repository: GitOperationRepository = Depends(get_git_operation_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> GitFinalizationService:
    return GitFinalizationService(
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
    )


def get_report_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    project_service: ProjectService = Depends(get_project_service),
    finding_repository: FindingRepository = Depends(get_finding_repository),
    issue_group_repository: IssueGroupRepository = Depends(get_issue_group_repository),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    risk_decision_repository: RiskDecisionRepository = Depends(get_risk_decision_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    self_correction_cycle_repository: SelfCorrectionCycleRepository = Depends(
        get_self_correction_cycle_repository,
    ),
    regression_test_result_repository: RegressionTestResultRepository = Depends(
        get_regression_test_result_repository,
    ),
    peer_review_result_repository: PeerReviewResultRepository = Depends(
        get_peer_review_result_repository,
    ),
    approval_repository: ApprovalRepository = Depends(get_approval_repository),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    git_operation_repository: GitOperationRepository = Depends(get_git_operation_repository),
    report_repository: ReportRepository = Depends(get_report_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> ReportService:
    return ReportService(
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
    )


def get_fix_planner_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    finding_repository: FindingRepository = Depends(get_finding_repository),
    issue_group_repository: IssueGroupRepository = Depends(get_issue_group_repository),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    memory_service: MemoryService = Depends(get_memory_service),
) -> FixPlannerService:
    return FixPlannerService(
        run_repository=run_repository,
        run_service=run_service,
        finding_repository=finding_repository,
        issue_group_repository=issue_group_repository,
        fix_plan_repository=fix_plan_repository,
        event_repository=event_repository,
        memory_service=memory_service,
    )


def get_risk_assessment_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    risk_decision_repository: RiskDecisionRepository = Depends(get_risk_decision_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> RiskAssessmentService:
    return RiskAssessmentService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        event_repository=event_repository,
    )


def get_code_fix_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    risk_decision_repository: RiskDecisionRepository = Depends(get_risk_decision_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    app_settings: Settings = Depends(get_settings),
) -> CodeFixService:
    return CodeFixService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        event_repository=event_repository,
        scanner_timeout_seconds=app_settings.scanner_timeout_seconds,
    )


def get_verification_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    app_settings: Settings = Depends(get_settings),
) -> VerificationService:
    return VerificationService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        event_repository=event_repository,
        scanner_timeout_seconds=app_settings.scanner_timeout_seconds,
    )


def get_self_correction_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    risk_decision_repository: RiskDecisionRepository = Depends(get_risk_decision_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    self_correction_cycle_repository: SelfCorrectionCycleRepository = Depends(
        get_self_correction_cycle_repository,
    ),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    app_settings: Settings = Depends(get_settings),
) -> SelfCorrectionService:
    return SelfCorrectionService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        risk_decision_repository=risk_decision_repository,
        fix_attempt_repository=fix_attempt_repository,
        verification_result_repository=verification_result_repository,
        self_correction_cycle_repository=self_correction_cycle_repository,
        event_repository=event_repository,
        scanner_timeout_seconds=app_settings.scanner_timeout_seconds,
        max_fix_iterations=app_settings.max_fix_iterations,
    )


def get_regression_test_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    regression_test_result_repository: RegressionTestResultRepository = Depends(
        get_regression_test_result_repository,
    ),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    app_settings: Settings = Depends(get_settings),
) -> RegressionTestService:
    return RegressionTestService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        verification_result_repository=verification_result_repository,
        regression_test_result_repository=regression_test_result_repository,
        event_repository=event_repository,
        scanner_timeout_seconds=app_settings.scanner_timeout_seconds,
    )


def get_peer_review_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    regression_test_result_repository: RegressionTestResultRepository = Depends(
        get_regression_test_result_repository,
    ),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    peer_review_result_repository: PeerReviewResultRepository = Depends(
        get_peer_review_result_repository,
    ),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> PeerReviewService:
    return PeerReviewService(
        run_repository=run_repository,
        run_service=run_service,
        fix_plan_repository=fix_plan_repository,
        fix_attempt_repository=fix_attempt_repository,
        regression_test_result_repository=regression_test_result_repository,
        verification_result_repository=verification_result_repository,
        peer_review_result_repository=peer_review_result_repository,
        event_repository=event_repository,
    )


def get_human_approval_service(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    fix_plan_repository: FixPlanRepository = Depends(get_fix_plan_repository),
    risk_decision_repository: RiskDecisionRepository = Depends(get_risk_decision_repository),
    fix_attempt_repository: FixAttemptRepository = Depends(get_fix_attempt_repository),
    verification_result_repository: VerificationResultRepository = Depends(
        get_verification_result_repository,
    ),
    peer_review_result_repository: PeerReviewResultRepository = Depends(
        get_peer_review_result_repository,
    ),
    self_correction_cycle_repository: SelfCorrectionCycleRepository = Depends(
        get_self_correction_cycle_repository,
    ),
    approval_repository: ApprovalRepository = Depends(get_approval_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
) -> HumanApprovalService:
    return HumanApprovalService(
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


def get_git_service(
    project_service: ProjectService = Depends(get_project_service),
    git_credential_service: GitCredentialService = Depends(get_git_credential_service),
    provider_factory: GitProviderFactory = Depends(get_git_provider_factory),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
    run_service: RunService = Depends(get_run_service),
    app_settings: Settings = Depends(get_settings),
) -> GitService:
    return GitService(
        project_service=project_service,
        git_credential_service=git_credential_service,
        provider_factory=provider_factory,
        workspace_manager=workspace_manager,
        run_service=run_service,
        app_settings=app_settings,
    )


def get_root_orchestrator(
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    git_service: GitService = Depends(get_git_service),
    intelligence_service: ProjectIntelligenceService = Depends(get_project_intelligence_service),
    diagnostic_agent_service: DiagnosticAgentService = Depends(get_diagnostic_agent_service),
    issue_correlation_service: IssueCorrelationService = Depends(get_issue_correlation_service),
    fix_planner_service: FixPlannerService = Depends(get_fix_planner_service),
    risk_assessment_service: RiskAssessmentService = Depends(get_risk_assessment_service),
    code_fix_service: CodeFixService = Depends(get_code_fix_service),
    verification_service: VerificationService = Depends(get_verification_service),
    self_correction_service: SelfCorrectionService = Depends(get_self_correction_service),
    regression_test_service: RegressionTestService = Depends(get_regression_test_service),
    peer_review_service: PeerReviewService = Depends(get_peer_review_service),
    human_approval_service: HumanApprovalService = Depends(get_human_approval_service),
    memory_service: MemoryService = Depends(get_memory_service),
    git_finalization_service: GitFinalizationService = Depends(get_git_finalization_service),
    report_service: ReportService = Depends(get_report_service),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    state_repository: AgentStateRepository = Depends(get_agent_state_repository),
    app_settings: Settings = Depends(get_settings),
) -> GoogleAdkOrchestrator:
    services = build_service_container(
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
    )
    return build_google_adk_orchestrator(app_settings, services)


def get_orchestration_service(
    run_repository: RunRepository = Depends(get_run_repository),
    orchestrator: GoogleAdkOrchestrator = Depends(get_root_orchestrator),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    state_repository: AgentStateRepository = Depends(get_agent_state_repository),
) -> OrchestrationService:
    return OrchestrationService(
        run_repository=run_repository,
        orchestrator=orchestrator,
        event_repository=event_repository,
        state_repository=state_repository,
    )


def get_run_progress_stream_service(
    run_repository: RunRepository = Depends(get_run_repository),
    event_repository: AgentEventRepository = Depends(get_agent_event_repository),
    state_repository: AgentStateRepository = Depends(get_agent_state_repository),
) -> RunProgressStreamService:
    return RunProgressStreamService(
        run_repository=run_repository,
        event_repository=event_repository,
        state_repository=state_repository,
    )


def get_chat_service(
    app_settings: Settings = Depends(get_settings),
    run_repository: RunRepository = Depends(get_run_repository),
    run_service: RunService = Depends(get_run_service),
    project_service: ProjectService = Depends(get_project_service),
    chat_message_repository: ChatMessageRepository = Depends(get_chat_message_repository),
    finding_repository: FindingRepository = Depends(get_finding_repository),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
    report_repository: ReportRepository = Depends(get_report_repository),
) -> ChatService:
    return ChatService(
        settings=app_settings,
        run_repository=run_repository,
        run_service=run_service,
        project_service=project_service,
        chat_message_repository=chat_message_repository,
        finding_repository=finding_repository,
        memory_repository=memory_repository,
        report_repository=report_repository,
        gemini_client=GeminiChatClient(app_settings),
    )
