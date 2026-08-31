import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.report_agent import ReportAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.reporting.markdown_builder import (
    ReportGenerationContext,
    compute_execution_duration_ms,
    compute_final_health_score,
    extract_tool_versions,
)
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.approval_repository import ApprovalRepository
from app.db.repositories.finding_repository import FindingRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.git_operation_repository import GitOperationRepository
from app.db.repositories.issue_group_repository import IssueGroupRepository
from app.db.repositories.memory_repository import MemoryRepository
from app.db.repositories.peer_review_result_repository import PeerReviewResultRepository
from app.db.repositories.regression_test_result_repository import RegressionTestResultRepository
from app.db.repositories.report_repository import ReportRepository
from app.db.repositories.risk_decision_repository import RiskDecisionRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.agent_event import AgentEventType
from app.models.git_operation_enums import GitOperationStatus
from app.models.report_enums import ReportStatus
from app.models.run import RunStatus
from app.models.run_report import RunReport
from app.models.scan import BaselineDiagnosticsSummary
from app.schemas.report import (
    GenerateRunReportResponse,
    RunReportMarkdownResponse,
    RunReportResponse,
)
from app.services.baseline_scan_service import BASELINE_SUMMARY_NAME
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.workspace.exceptions import WorkspaceNotFoundError
from app.workspace.artifact_reader import (
    WorkspaceArtifactAccessError,
    WorkspaceArtifactNotFoundError,
    read_workspace_text_file,
)

logger = get_logger(__name__)

RUN_REPORT_ARTIFACT_NAME = "run_report.json"


class RunNotReadyForReportError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class RunReportNotFoundError(Exception):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.message = f"No report available for run: {run_id}"
        super().__init__(self.message)


class ReportService:
    """Generate markdown and PDF reports for completed autonomous runs."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        project_service: ProjectService,
        finding_repository: FindingRepository,
        issue_group_repository: IssueGroupRepository,
        fix_plan_repository: FixPlanRepository,
        risk_decision_repository: RiskDecisionRepository,
        fix_attempt_repository: FixAttemptRepository,
        verification_result_repository: VerificationResultRepository,
        self_correction_cycle_repository: SelfCorrectionCycleRepository,
        regression_test_result_repository: RegressionTestResultRepository,
        peer_review_result_repository: PeerReviewResultRepository,
        approval_repository: ApprovalRepository,
        memory_repository: MemoryRepository,
        git_operation_repository: GitOperationRepository,
        report_repository: ReportRepository,
        event_repository: AgentEventRepository,
        report_agent: ReportAgent | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._project_service = project_service
        self._finding_repository = finding_repository
        self._issue_group_repository = issue_group_repository
        self._fix_plan_repository = fix_plan_repository
        self._risk_decision_repository = risk_decision_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._verification_result_repository = verification_result_repository
        self._self_correction_cycle_repository = self_correction_cycle_repository
        self._regression_test_result_repository = regression_test_result_repository
        self._peer_review_result_repository = peer_review_result_repository
        self._approval_repository = approval_repository
        self._memory_repository = memory_repository
        self._git_operation_repository = git_operation_repository
        self._report_repository = report_repository
        self._event_repository = event_repository
        self._report_agent = report_agent or ReportAgent()

    def generate_run_report(
        self,
        user_id: str,
        run_id: str,
        *,
        allow_without_git: bool = False,
    ) -> GenerateRunReportResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        self._validate_prerequisites(run_id, run.status, allow_without_git=allow_without_git)
        project = self._project_service.get_project(user_id, run.project_id)
        repository = None
        if run.repository_id is not None:
            repository = self._project_service.get_repository(
                user_id,
                run.project_id,
                run.repository_id,
            )

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        findings = self._finding_repository.list_by_run(run_id)
        verification_results = self._verification_result_repository.list_by_run(run_id)
        peer_reviews = self._peer_review_result_repository.list_by_run(run_id)
        baseline_summary = _load_baseline_summary(workspace.baseline, run_id)
        duration_ms = compute_execution_duration_ms(run, baseline_summary)
        final_health_score = compute_final_health_score(
            findings,
            verification_results,
            peer_reviews,
        )
        tool_versions = extract_tool_versions(baseline_summary)
        memories = self._memory_repository.list_by_project(run.project_id)
        git_operations = self._git_operation_repository.list_by_run(run_id)

        context = ReportGenerationContext(
            run=run,
            project=project,
            repository=repository,
            baseline_summary=baseline_summary,
            findings=findings,
            issue_groups=self._issue_group_repository.list_by_run(run_id),
            patch_plans=self._fix_plan_repository.list_by_run(run_id),
            risk_decisions=self._risk_decision_repository.list_by_run(run_id),
            fix_attempts=self._fix_attempt_repository.list_by_run(run_id),
            verification_results=verification_results,
            self_correction_cycles=self._self_correction_cycle_repository.list_by_run(run_id),
            regression_results=self._regression_test_result_repository.list_by_run(run_id),
            peer_reviews=peer_reviews,
            approvals=self._approval_repository.list_by_run(run_id),
            memories=memories,
            git_operations=git_operations,
            duration_ms=duration_ms,
            final_health_score=final_health_score,
            tool_versions=tool_versions,
        )

        self._emit_report_generation_started(run_id)
        started_at = datetime.now(UTC)
        output_dir = workspace.reports
        content, artifact_paths = self._report_agent.generate(context, output_dir)
        report = self._persist_report(
            run,
            content,
            artifact_paths.markdown_path,
            artifact_paths.pdf_path,
            workspace.baseline,
        )
        self._run_repository.update_status(run_id, user_id, RunStatus.COMPLETED)
        self._emit_report_generation_completed(run_id, report.report_id)
        self._emit_run_completed(run_id)

        completed_at = datetime.now(UTC)
        response = GenerateRunReportResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            report=RunReportResponse.model_validate(report.model_dump()),
            run_status=RunStatus.COMPLETED.value,
        )

        logger.info(
            "Run report generated",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "report_id": report.report_id,
                "stage": "reporting",
            },
        )
        return response

    def get_run_report(self, user_id: str, run_id: str) -> RunReportResponse | None:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        report = self._get_persisted_report(user_id, run_id)
        if report is None:
            return None

        try:
            return RunReportResponse.model_validate(report.model_dump())
        except Exception as exc:
            logger.exception(
                "Stored run report failed validation",
                extra={"run_id": run_id, "user_id": user_id},
            )
            raise RunReportNotFoundError(run_id) from exc

    def get_run_report_markdown(self, user_id: str, run_id: str) -> RunReportMarkdownResponse:
        report = self.get_run_report(user_id, run_id)
        if report is None:
            raise RunReportNotFoundError(run_id)

        try:
            workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        except WorkspaceNotFoundError as exc:
            raise RunReportNotFoundError(run_id) from exc

        try:
            markdown = read_workspace_text_file(workspace.root, report.markdown_path)
        except (WorkspaceArtifactNotFoundError, WorkspaceArtifactAccessError) as exc:
            raise RunReportNotFoundError(run_id) from exc

        return RunReportMarkdownResponse(
            report_id=report.report_id,
            run_id=run_id,
            markdown=markdown,
        )

    def _get_persisted_report(self, user_id: str, run_id: str) -> RunReport | None:
        report = self._report_repository.get_by_run(run_id)
        if report is not None:
            return report
        return self._load_report_from_workspace(user_id, run_id)

    def _validate_prerequisites(
        self,
        run_id: str,
        status: RunStatus,
        *,
        allow_without_git: bool = False,
    ) -> None:
        if allow_without_git:
            if status == RunStatus.FAILED:
                raise RunNotReadyForReportError("Cannot generate report for a failed run")
            return

        if status not in {RunStatus.REPORTING, RunStatus.COMPLETED}:
            raise RunNotReadyForReportError(
                "Run must be in REPORTING before generating the final report",
            )

        if status != RunStatus.COMPLETED:
            git_operations = self._git_operation_repository.list_by_run(run_id)
            if not any(
                operation.status == GitOperationStatus.PR_CREATED for operation in git_operations
            ):
                raise RunNotReadyForReportError(
                    "Git finalization must complete successfully before report generation",
                )

    def _persist_report(
        self,
        run,
        content,
        markdown_path: Path,
        pdf_path: Path,
        baseline_dir: Path,
    ) -> RunReport:
        report_id = str(ObjectId())
        artifact_path = baseline_dir / RUN_REPORT_ARTIFACT_NAME
        report = RunReport(
            report_id=report_id,
            run_id=run.id,
            project_id=run.project_id,
            status=ReportStatus.GENERATED,
            markdown_path=str(markdown_path),
            pdf_path=str(pdf_path),
            final_health_score=content.final_health_score,
            pull_request_url=content.pull_request_url,
            branch_name=content.branch_name,
            commit_sha=content.commit_sha,
            duration_ms=content.duration_ms,
            tool_versions=content.tool_versions,
            artifact_path=str(artifact_path),
            created_at=datetime.now(UTC),
        )
        artifact_path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._report_repository.upsert_for_run(report)

    def _emit_report_generation_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.REPORT_GENERATION_STARTED,
                stage=OrchestrationStage.REPORTING,
                agent="report_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_report_generation_completed(self, run_id: str, report_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.REPORT_GENERATION_COMPLETED,
                stage=OrchestrationStage.REPORTING,
                agent="report_agent",
                payload={"run_id": run_id, "report_id": report_id},
            ),
        )

    def _emit_run_completed(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.RUN_COMPLETED,
                stage=OrchestrationStage.REPORTING,
                agent="report_agent",
                payload={"run_id": run_id},
            ),
        )

    def _load_report_from_workspace(self, user_id: str, run_id: str) -> RunReport | None:
        try:
            workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        except WorkspaceNotFoundError:
            return None

        artifact_path = workspace.baseline / RUN_REPORT_ARTIFACT_NAME
        if not artifact_path.is_file():
            return None

        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        report = RunReport.model_validate(payload)
        return self._report_repository.upsert_for_run(report)


def _load_baseline_summary(baseline_dir: Path, run_id: str) -> BaselineDiagnosticsSummary | None:
    summary_path = baseline_dir / BASELINE_SUMMARY_NAME
    if not summary_path.is_file():
        return None
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return BaselineDiagnosticsSummary.model_validate(payload)
