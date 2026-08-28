from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from google.genai.errors import ClientError

from app.api.dependencies import (
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
    get_regression_test_service,
    get_report_service,
    get_risk_assessment_service,
    get_run_progress_stream_service,
    get_run_service,
    get_self_correction_service,
    get_verification_service,
)
from app.api.dependencies.auth import get_current_active_user
from app.db.repositories.approval_repository import ApprovalNotFoundError
from app.db.repositories.fix_attempt_repository import FixAttemptNotFoundError
from app.db.repositories.fix_plan_repository import FixPlanNotFoundError
from app.db.repositories.git_operation_repository import GitOperationNotFoundError
from app.db.repositories.peer_review_result_repository import PeerReviewResultNotFoundError
from app.db.repositories.project_repository import ProjectNotFoundError
from app.db.repositories.regression_test_result_repository import RegressionTestResultNotFoundError
from app.db.repositories.risk_decision_repository import RiskDecisionNotFoundError
from app.db.repositories.run_repository import RunNotFoundError
from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleNotFoundError
from app.db.repositories.verification_result_repository import VerificationResultNotFoundError
from app.intelligence import RepositoryEmptyError, RepositoryNotReadyError
from app.models.approval_enums import ApprovalTrigger, HumanDecision
from app.models.run import RunStatus
from app.models.user import User
from app.schemas.approval import (
    ApprovalDiffResponse,
    HumanApprovalResponse,
    PrepareApprovalsResponse,
    SubmitApprovalDecisionRequest,
    SubmitApprovalDecisionResponse,
)
from app.schemas.finding import (
    DiagnosticAgentsResponse,
    FindingResponse,
    RunDiagnosticAgentsRequest,
)
from app.schemas.fix_attempt import (
    CodeFixResponse,
    FixAttemptDiffResponse,
    FixAttemptResponse,
)
from app.schemas.git import RepositoryCloneRequest, RepositoryCloneResponse
from app.schemas.git_finalization import (
    GitFinalizationRequest,
    GitOperationResponse,
    RunGitFinalizationResponse,
)
from app.schemas.issue_group import IssueCorrelationResponse, IssueGroupResponse
from app.schemas.memory import CaptureRunMemoryResponse
from app.schemas.orchestration import (
    AgentEventResponse,
    RunAgentStateResponse,
    RunOrchestrationRequest,
    RunOrchestrationResponse,
)
from app.schemas.patch_plan import FixPlanningResponse, PatchPlanResponse
from app.schemas.peer_review import PeerReviewResultResponse, RunPeerReviewResponse
from app.schemas.project_intelligence import ProjectIntelligenceArtifactResponse
from app.schemas.regression_test import RegressionTestResultResponse, RunRegressionTestResponse
from app.schemas.report import GenerateRunReportResponse, RunReportMarkdownResponse, RunReportResponse
from app.schemas.risk_decision import RiskAssessmentResponse, RiskDecisionResponse
from app.schemas.run import RunCreate, RunResponse, RunWorkspaceResponse
from app.schemas.scan import BaselineDiagnosticsResponse, RunScannerRequest
from app.schemas.self_correction import RunSelfCorrectionResponse, SelfCorrectionCycleResponse
from app.schemas.verification_result import RunVerificationResponse, VerificationResultResponse
from app.services.baseline_scan_service import BaselineDiagnosticsNotFoundError, BaselineScanService
from app.services.code_fix_service import (
    CodeFixService,
    FixAttemptDiffNotFoundError,
    RiskDecisionsRequiredError,
)
from app.services.diagnostic_agent_service import DiagnosticAgentService
from app.services.fix_planner_service import FixPlannerService, IssueGroupsRequiredError
from app.services.git_finalization_service import (
    GitFinalizationService,
    RunNotReadyForGitFinalizationError,
)
from app.services.git_service import GitService
from app.services.human_approval_service import (
    ApprovalAlreadyDecidedError,
    ApprovalDiffNotFoundError,
    FeedbackRequiredError,
    HumanApprovalService,
    RunNotAwaitingApprovalError,
)
from app.services.issue_correlation_service import IssueCorrelationService
from app.services.memory_service import MemoryService
from app.services.orchestration_service import AgentStateNotFoundError, OrchestrationService
from app.services.peer_review_service import PeerReviewService, RegressionTestsRequiredError
from app.services.project_intelligence_service import ProjectIntelligenceService
from app.services.regression_test_service import (
    PassedVerificationsRequiredError,
    RegressionTestService,
)
from app.services.report_service import (
    ReportService,
    RunNotReadyForReportError,
    RunReportNotFoundError,
)
from app.services.risk_assessment_service import PatchPlansRequiredError, RiskAssessmentService
from app.services.run_progress_stream_service import RunProgressStreamService
from app.services.run_service import RunService
from app.services.self_correction_service import (
    SelfCorrectionService,
    VerificationFailuresRequiredError,
)
from app.services.verification_service import FixAttemptsRequiredError, VerificationService

router = APIRouter()


def _run_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


def _project_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


async def _resume_run_after_risk_gate_approval(
    orchestration_service: OrchestrationService,
    user_id: str,
    run_id: str,
) -> None:
    await orchestration_service.execute_run(
        user_id,
        run_id,
        skip_clone=True,
        resume_after_approval=True,
    )


def _gemini_rate_limit_http_exception(exc: BaseException) -> HTTPException | None:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, ClientError) and current.code == 429:
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Gemini API rate limit exceeded. Wait a minute and retry, check your "
                    "quota at https://aistudio.google.com/, or set "
                    "CODETHERA_GEMINI_MODEL=gemini-2.5-flash in backend/.env."
                ),
            )
        current = current.__cause__
    return None


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreate,
    current_user: User = Depends(get_current_active_user),
    run_service: RunService = Depends(get_run_service),
) -> RunResponse:
    try:
        return run_service.create_run(current_user.id, payload)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.get("", response_model=list[RunResponse])
async def list_runs(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    run_service: RunService = Depends(get_run_service),
) -> list[RunResponse]:
    try:
        return run_service.list_runs(current_user.id, project_id)
    except ProjectNotFoundError as exc:
        raise _project_not_found() from exc


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    run_service: RunService = Depends(get_run_service),
) -> RunResponse:
    try:
        return run_service.get_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/workspace", response_model=RunWorkspaceResponse)
async def get_run_workspace(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    run_service: RunService = Depends(get_run_service),
) -> RunWorkspaceResponse:
    try:
        return run_service.get_run_workspace(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.post("/{run_id}/clone", response_model=RepositoryCloneResponse)
async def clone_run_repository(
    run_id: str,
    payload: RepositoryCloneRequest,
    current_user: User = Depends(get_current_active_user),
    git_service: GitService = Depends(get_git_service),
) -> RepositoryCloneResponse:
    try:
        result = git_service.clone_run_repository(
            current_user.id,
            run_id,
            branch=payload.branch,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message or "Clone failed",
        )

    return RepositoryCloneResponse(
        success=result.success,
        destination=str(result.destination),
        branch=result.branch,
        commit_sha=result.commit_sha,
        message=result.message,
    )


@router.post("/{run_id}/analyze", response_model=ProjectIntelligenceArtifactResponse)
async def analyze_run_repository(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    intelligence_service: ProjectIntelligenceService = Depends(get_project_intelligence_service),
) -> ProjectIntelligenceArtifactResponse:
    try:
        return intelligence_service.analyze_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except (RepositoryNotReadyError, RepositoryEmptyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/intelligence", response_model=ProjectIntelligenceArtifactResponse)
async def get_run_intelligence(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    intelligence_service: ProjectIntelligenceService = Depends(get_project_intelligence_service),
) -> ProjectIntelligenceArtifactResponse:
    try:
        return intelligence_service.get_intelligence(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RepositoryNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.post("/{run_id}/diagnostics", response_model=BaselineDiagnosticsResponse)
async def run_baseline_diagnostics(
    run_id: str,
    payload: RunScannerRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    baseline_scan_service: BaselineScanService = Depends(get_baseline_scan_service),
) -> BaselineDiagnosticsResponse:
    try:
        return baseline_scan_service.run_diagnostics(
            current_user.id,
            run_id,
            tools=payload.tools if payload else None,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RepositoryNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/diagnostics", response_model=BaselineDiagnosticsResponse)
async def get_baseline_diagnostics(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    baseline_scan_service: BaselineScanService = Depends(get_baseline_scan_service),
) -> BaselineDiagnosticsResponse:
    try:
        return baseline_scan_service.get_diagnostics(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except BaselineDiagnosticsNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.post("/{run_id}/agents", response_model=DiagnosticAgentsResponse)
async def run_diagnostic_agents(
    run_id: str,
    payload: RunDiagnosticAgentsRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    diagnostic_agent_service: DiagnosticAgentService = Depends(get_diagnostic_agent_service),
) -> DiagnosticAgentsResponse:
    try:
        return diagnostic_agent_service.run_agents(
            current_user.id,
            run_id,
            agents=payload.agents if payload else None,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RepositoryNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/findings", response_model=list[FindingResponse])
async def list_run_findings(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    diagnostic_agent_service: DiagnosticAgentService = Depends(get_diagnostic_agent_service),
) -> list[FindingResponse]:
    try:
        return diagnostic_agent_service.list_findings(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.post("/{run_id}/correlate", response_model=IssueCorrelationResponse)
async def correlate_run_findings(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    issue_correlation_service: IssueCorrelationService = Depends(get_issue_correlation_service),
) -> IssueCorrelationResponse:
    try:
        return issue_correlation_service.correlate_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/issues", response_model=list[IssueGroupResponse])
async def list_run_issue_groups(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    issue_correlation_service: IssueCorrelationService = Depends(get_issue_correlation_service),
) -> list[IssueGroupResponse]:
    try:
        return issue_correlation_service.list_issue_groups(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.post("/{run_id}/plan", response_model=FixPlanningResponse)
async def plan_run_fixes(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    fix_planner_service: FixPlannerService = Depends(get_fix_planner_service),
) -> FixPlanningResponse:
    try:
        return fix_planner_service.plan_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except IssueGroupsRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/plans", response_model=list[PatchPlanResponse])
async def list_run_patch_plans(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    fix_planner_service: FixPlannerService = Depends(get_fix_planner_service),
) -> list[PatchPlanResponse]:
    try:
        return fix_planner_service.list_patch_plans(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/plans/{patch_plan_id}", response_model=PatchPlanResponse)
async def get_run_patch_plan(
    run_id: str,
    patch_plan_id: str,
    current_user: User = Depends(get_current_active_user),
    fix_planner_service: FixPlannerService = Depends(get_fix_planner_service),
) -> PatchPlanResponse:
    try:
        return fix_planner_service.get_patch_plan(current_user.id, run_id, patch_plan_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except FixPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/assess-risk", response_model=RiskAssessmentResponse)
async def assess_run_risk(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    risk_assessment_service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> RiskAssessmentResponse:
    try:
        return risk_assessment_service.assess_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except PatchPlansRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/risk-decisions", response_model=list[RiskDecisionResponse])
async def list_run_risk_decisions(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    risk_assessment_service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> list[RiskDecisionResponse]:
    try:
        return risk_assessment_service.list_risk_decisions(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/risk-decisions/{risk_decision_id}", response_model=RiskDecisionResponse)
async def get_run_risk_decision(
    run_id: str,
    risk_decision_id: str,
    current_user: User = Depends(get_current_active_user),
    risk_assessment_service: RiskAssessmentService = Depends(get_risk_assessment_service),
) -> RiskDecisionResponse:
    try:
        return risk_assessment_service.get_risk_decision(
            current_user.id,
            run_id,
            risk_decision_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RiskDecisionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/fix", response_model=CodeFixResponse)
async def apply_run_fixes(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    code_fix_service: CodeFixService = Depends(get_code_fix_service),
) -> CodeFixResponse:
    try:
        return code_fix_service.fix_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RiskDecisionsRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/fix-attempts", response_model=list[FixAttemptResponse])
async def list_run_fix_attempts(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    code_fix_service: CodeFixService = Depends(get_code_fix_service),
) -> list[FixAttemptResponse]:
    try:
        return code_fix_service.list_fix_attempts(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/fix-attempts/{fix_attempt_id}", response_model=FixAttemptResponse)
async def get_run_fix_attempt(
    run_id: str,
    fix_attempt_id: str,
    current_user: User = Depends(get_current_active_user),
    code_fix_service: CodeFixService = Depends(get_code_fix_service),
) -> FixAttemptResponse:
    try:
        return code_fix_service.get_fix_attempt(current_user.id, run_id, fix_attempt_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except FixAttemptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{run_id}/fix-attempts/{fix_attempt_id}/diff",
    response_model=FixAttemptDiffResponse,
)
async def get_run_fix_attempt_diff(
    run_id: str,
    fix_attempt_id: str,
    current_user: User = Depends(get_current_active_user),
    code_fix_service: CodeFixService = Depends(get_code_fix_service),
) -> FixAttemptDiffResponse:
    try:
        return code_fix_service.get_fix_attempt_diff(
            current_user.id,
            run_id,
            fix_attempt_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except FixAttemptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except FixAttemptDiffNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/verify", response_model=RunVerificationResponse)
async def verify_run_fixes(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    verification_service: VerificationService = Depends(get_verification_service),
) -> RunVerificationResponse:
    try:
        return verification_service.verify_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except FixAttemptsRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/verification-results", response_model=list[VerificationResultResponse])
async def list_run_verification_results(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    verification_service: VerificationService = Depends(get_verification_service),
) -> list[VerificationResultResponse]:
    try:
        return verification_service.list_verification_results(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get(
    "/{run_id}/verification-results/{verification_result_id}",
    response_model=VerificationResultResponse,
)
async def get_run_verification_result(
    run_id: str,
    verification_result_id: str,
    current_user: User = Depends(get_current_active_user),
    verification_service: VerificationService = Depends(get_verification_service),
) -> VerificationResultResponse:
    try:
        return verification_service.get_verification_result(
            current_user.id,
            run_id,
            verification_result_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except VerificationResultNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/self-correct", response_model=RunSelfCorrectionResponse)
async def self_correct_run(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    self_correction_service: SelfCorrectionService = Depends(get_self_correction_service),
) -> RunSelfCorrectionResponse:
    try:
        return self_correction_service.correct_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except VerificationFailuresRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/self-correction-cycles", response_model=list[SelfCorrectionCycleResponse])
async def list_run_self_correction_cycles(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    self_correction_service: SelfCorrectionService = Depends(get_self_correction_service),
) -> list[SelfCorrectionCycleResponse]:
    try:
        return self_correction_service.list_self_correction_cycles(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get(
    "/{run_id}/self-correction-cycles/{self_correction_cycle_id}",
    response_model=SelfCorrectionCycleResponse,
)
async def get_run_self_correction_cycle(
    run_id: str,
    self_correction_cycle_id: str,
    current_user: User = Depends(get_current_active_user),
    self_correction_service: SelfCorrectionService = Depends(get_self_correction_service),
) -> SelfCorrectionCycleResponse:
    try:
        return self_correction_service.get_self_correction_cycle(
            current_user.id,
            run_id,
            self_correction_cycle_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except SelfCorrectionCycleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/regression-tests", response_model=RunRegressionTestResponse)
async def run_regression_tests(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    regression_test_service: RegressionTestService = Depends(get_regression_test_service),
) -> RunRegressionTestResponse:
    try:
        return regression_test_service.run_regression_tests(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except PassedVerificationsRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/regression-tests", response_model=list[RegressionTestResultResponse])
async def list_run_regression_tests(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    regression_test_service: RegressionTestService = Depends(get_regression_test_service),
) -> list[RegressionTestResultResponse]:
    try:
        return regression_test_service.list_regression_tests(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get(
    "/{run_id}/regression-tests/{regression_test_id}",
    response_model=RegressionTestResultResponse,
)
async def get_run_regression_test(
    run_id: str,
    regression_test_id: str,
    current_user: User = Depends(get_current_active_user),
    regression_test_service: RegressionTestService = Depends(get_regression_test_service),
) -> RegressionTestResultResponse:
    try:
        return regression_test_service.get_regression_test(
            current_user.id,
            run_id,
            regression_test_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RegressionTestResultNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/peer-review", response_model=RunPeerReviewResponse)
async def review_run_patches(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    peer_review_service: PeerReviewService = Depends(get_peer_review_service),
) -> RunPeerReviewResponse:
    try:
        return peer_review_service.review_run(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RegressionTestsRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/peer-reviews", response_model=list[PeerReviewResultResponse])
async def list_run_peer_reviews(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    peer_review_service: PeerReviewService = Depends(get_peer_review_service),
) -> list[PeerReviewResultResponse]:
    try:
        return peer_review_service.list_peer_reviews(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get(
    "/{run_id}/peer-reviews/{peer_review_id}",
    response_model=PeerReviewResultResponse,
)
async def get_run_peer_review(
    run_id: str,
    peer_review_id: str,
    current_user: User = Depends(get_current_active_user),
    peer_review_service: PeerReviewService = Depends(get_peer_review_service),
) -> PeerReviewResultResponse:
    try:
        return peer_review_service.get_peer_review(
            current_user.id,
            run_id,
            peer_review_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except PeerReviewResultNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/approvals/prepare", response_model=PrepareApprovalsResponse)
async def prepare_run_approvals(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    human_approval_service: HumanApprovalService = Depends(get_human_approval_service),
) -> PrepareApprovalsResponse:
    try:
        return human_approval_service.prepare_approvals(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RunNotAwaitingApprovalError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/approvals", response_model=list[HumanApprovalResponse])
async def list_run_approvals(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    human_approval_service: HumanApprovalService = Depends(get_human_approval_service),
) -> list[HumanApprovalResponse]:
    try:
        return human_approval_service.list_approvals(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/approvals/{approval_id}", response_model=HumanApprovalResponse)
async def get_run_approval(
    run_id: str,
    approval_id: str,
    current_user: User = Depends(get_current_active_user),
    human_approval_service: HumanApprovalService = Depends(get_human_approval_service),
) -> HumanApprovalResponse:
    try:
        return human_approval_service.get_approval(current_user.id, run_id, approval_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{run_id}/approvals/{approval_id}/diff",
    response_model=ApprovalDiffResponse,
)
async def get_run_approval_diff(
    run_id: str,
    approval_id: str,
    current_user: User = Depends(get_current_active_user),
    human_approval_service: HumanApprovalService = Depends(get_human_approval_service),
) -> ApprovalDiffResponse:
    try:
        return human_approval_service.get_approval_diff(
            current_user.id,
            run_id,
            approval_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ApprovalDiffNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{run_id}/approvals/{approval_id}/decide",
    response_model=SubmitApprovalDecisionResponse,
)
async def decide_run_approval(
    run_id: str,
    approval_id: str,
    payload: SubmitApprovalDecisionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    human_approval_service: HumanApprovalService = Depends(get_human_approval_service),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> SubmitApprovalDecisionResponse:
    try:
        response = human_approval_service.submit_decision(
            current_user.id,
            run_id,
            approval_id,
            payload,
        )
        if human_approval_service.should_resume_pipeline_after_decision(
            payload.decision,
            ApprovalTrigger(response.approval.trigger),
            RunStatus(response.run_status),
        ):
            background_tasks.add_task(
                _resume_run_after_risk_gate_approval,
                orchestration_service,
                current_user.id,
                run_id,
            )
        return response
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ApprovalAlreadyDecidedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FeedbackRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.post("/{run_id}/memory/capture", response_model=CaptureRunMemoryResponse)
async def capture_run_memory(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    memory_service: MemoryService = Depends(get_memory_service),
) -> CaptureRunMemoryResponse:
    try:
        return memory_service.capture_run_memory(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.post("/{run_id}/git/finalize", response_model=RunGitFinalizationResponse)
async def finalize_run_git(
    run_id: str,
    payload: GitFinalizationRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    git_finalization_service: GitFinalizationService = Depends(get_git_finalization_service),
) -> RunGitFinalizationResponse:
    try:
        return git_finalization_service.finalize_run(
            current_user.id,
            run_id,
            base_branch=payload.base_branch if payload else None,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RunNotReadyForGitFinalizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/git/operations", response_model=list[GitOperationResponse])
async def list_git_operations(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    git_finalization_service: GitFinalizationService = Depends(get_git_finalization_service),
) -> list[GitOperationResponse]:
    try:
        return git_finalization_service.list_git_operations(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/git/operations/{git_operation_id}", response_model=GitOperationResponse)
async def get_git_operation(
    run_id: str,
    git_operation_id: str,
    current_user: User = Depends(get_current_active_user),
    git_finalization_service: GitFinalizationService = Depends(get_git_finalization_service),
) -> GitOperationResponse:
    try:
        return git_finalization_service.get_git_operation(
            current_user.id,
            run_id,
            git_operation_id,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except GitOperationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{run_id}/reports/generate", response_model=GenerateRunReportResponse)
async def generate_run_report(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    report_service: ReportService = Depends(get_report_service),
) -> GenerateRunReportResponse:
    try:
        return report_service.generate_run_report(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RunNotReadyForReportError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/reports/markdown", response_model=RunReportMarkdownResponse)
async def get_run_report_markdown(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    report_service: ReportService = Depends(get_report_service),
) -> RunReportMarkdownResponse:
    try:
        return report_service.get_run_report_markdown(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except RunReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc


@router.get("/{run_id}/reports", response_model=RunReportResponse | None)
async def get_run_report(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    report_service: ReportService = Depends(get_report_service),
) -> RunReportResponse | None:
    try:
        return report_service.get_run_report(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.post("/{run_id}/execute", response_model=RunOrchestrationResponse)
async def execute_run_orchestration(
    run_id: str,
    payload: RunOrchestrationRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> RunOrchestrationResponse:
    try:
        request = payload or RunOrchestrationRequest()
        return await orchestration_service.execute_run(
            current_user.id,
            run_id,
            branch=request.branch,
            skip_clone=request.skip_clone,
            agents=request.agents,
            resume_after_approval=request.resume_after_approval,
        )
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except Exception as exc:
        rate_limit = _gemini_rate_limit_http_exception(exc)
        if rate_limit is not None:
            raise rate_limit from exc
        raise


@router.get("/{run_id}/events", response_model=list[AgentEventResponse])
async def list_run_events(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> list[AgentEventResponse]:
    try:
        return orchestration_service.list_events(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc


@router.get("/{run_id}/stream")
async def stream_run_progress(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    stream_service: RunProgressStreamService = Depends(get_run_progress_stream_service),
) -> StreamingResponse:
    try:
        stream = stream_service.stream_run_progress(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{run_id}/state", response_model=RunAgentStateResponse)
async def get_run_orchestration_state(
    run_id: str,
    current_user: User = Depends(get_current_active_user),
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> RunAgentStateResponse:
    try:
        return orchestration_service.get_state(current_user.id, run_id)
    except RunNotFoundError as exc:
        raise _run_not_found() from exc
    except AgentStateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message,
        ) from exc
