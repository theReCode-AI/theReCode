import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.peer_review_agent import PeerReviewAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.peer_review.engine import PeerReviewEngine
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.peer_review_result_repository import (
    PeerReviewResultNotFoundError,
    PeerReviewResultRepository,
)
from app.db.repositories.regression_test_result_repository import RegressionTestResultRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.agent_event import AgentEventType
from app.models.patch_plan import PatchPlan
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.peer_review_result import PeerReviewResult
from app.models.regression_test_enums import RegressionTestStatus
from app.models.regression_test_result import RegressionTestResult
from app.models.run import RunStatus
from app.schemas.peer_review import PeerReviewResultResponse, RunPeerReviewResponse
from app.services.regression_test_service import REGRESSION_TEST_RESULTS_ARTIFACT_NAME
from app.services.run_service import RunService

logger = get_logger(__name__)

PEER_REVIEW_RESULTS_ARTIFACT_NAME = "peer_review_results.json"


class RegressionTestsRequiredError(Exception):
    def __init__(
        self,
        message: str = "Regression test results are required before peer review",
    ) -> None:
        self.message = message
        super().__init__(message)


class PeerReviewService:
    """Run independent specialist reviewers and synthesize peer review decisions."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        fix_attempt_repository: FixAttemptRepository,
        regression_test_result_repository: RegressionTestResultRepository,
        verification_result_repository: VerificationResultRepository,
        peer_review_result_repository: PeerReviewResultRepository,
        event_repository: AgentEventRepository,
        peer_review_agent: PeerReviewAgent | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._regression_test_result_repository = regression_test_result_repository
        self._verification_result_repository = verification_result_repository
        self._peer_review_result_repository = peer_review_result_repository
        self._event_repository = event_repository
        self._peer_review_agent = peer_review_agent or PeerReviewAgent()

    def review_run(self, user_id: str, run_id: str) -> RunPeerReviewResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        regression_results = self._regression_test_result_repository.list_by_run(run_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        regression_artifact = workspace.baseline / REGRESSION_TEST_RESULTS_ARTIFACT_NAME
        review_targets = _completed_regression_targets(regression_results)
        if not review_targets and not regression_artifact.is_file():
            raise RegressionTestsRequiredError()
        if not review_targets:
            raise RegressionTestsRequiredError()

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        plans_by_id = {plan.patch_plan_id: plan for plan in patch_plans}
        fix_attempts = self._fix_attempt_repository.list_by_run(run_id)
        attempts_by_id = {attempt.fix_attempt_id: attempt for attempt in fix_attempts}
        verification_results = self._verification_result_repository.list_by_run(run_id)
        verifications_by_id = {
            result.verification_result_id: result for result in verification_results
        }
        engine = PeerReviewEngine()

        self._run_repository.update_status(run_id, user_id, RunStatus.PEER_REVIEW)
        self._emit_peer_review_started(run_id)
        started_at = datetime.now(UTC)
        persisted_results: list[PeerReviewResult] = []

        for patch_plan_id, regression_result in review_targets.items():
            patch_plan = plans_by_id.get(patch_plan_id)
            fix_attempt = attempts_by_id.get(regression_result.fix_attempt_id)
            verification_result = verifications_by_id.get(regression_result.verification_result_id)
            if patch_plan is None or fix_attempt is None or verification_result is None:
                continue

            output_dir = workspace.baseline / "peer_review" / patch_plan_id
            execution = self._peer_review_agent.run(
                workspace.working,
                patch_plan,
                fix_attempt,
                verification_result,
                regression_result,
                run.project_intelligence,
                engine,
            )
            result = self._persist_result(
                run_id,
                patch_plan,
                regression_result,
                execution,
                output_dir,
            )
            persisted_results.append(result)
            self._emit_peer_review_result_event(run_id, result)

        self._write_peer_review_results_artifact(workspace.baseline, run_id)
        next_status = self._resolve_run_status(persisted_results)
        self._run_repository.update_status(run_id, user_id, next_status)

        completed_at = datetime.now(UTC)
        response = RunPeerReviewResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            peer_reviews=[
                PeerReviewResultResponse.model_validate(result.model_dump())
                for result in persisted_results
            ],
            result_count=len(persisted_results),
            approved_count=sum(
                1 for result in persisted_results if result.verdict == PeerReviewVerdict.APPROVED
            ),
            changes_requested_count=sum(
                1
                for result in persisted_results
                if result.verdict == PeerReviewVerdict.CHANGES_REQUESTED
            ),
            rejected_count=sum(
                1 for result in persisted_results if result.verdict == PeerReviewVerdict.REJECTED
            ),
            run_status=next_status.value,
        )

        logger.info(
            "Peer review completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "result_count": response.result_count,
                "approved_count": response.approved_count,
                "changes_requested_count": response.changes_requested_count,
                "rejected_count": response.rejected_count,
                "stage": "peer_review",
            },
        )
        return response

    def list_peer_reviews(self, user_id: str, run_id: str) -> list[PeerReviewResultResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        results = self._peer_review_result_repository.list_by_run(run_id)
        return [
            PeerReviewResultResponse.model_validate(result.model_dump()) for result in results
        ]

    def get_peer_review(
        self,
        user_id: str,
        run_id: str,
        peer_review_id: str,
    ) -> PeerReviewResultResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        result = self._peer_review_result_repository.get_by_id_for_run(peer_review_id, run_id)
        if result is None:
            raise PeerReviewResultNotFoundError(peer_review_id)

        return PeerReviewResultResponse.model_validate(result.model_dump())

    def _persist_result(
        self,
        run_id: str,
        patch_plan: PatchPlan,
        regression_result: RegressionTestResult,
        execution,
        output_dir: Path,
    ) -> PeerReviewResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "result.json"

        result = PeerReviewResult(
            peer_review_id=str(ObjectId()),
            run_id=run_id,
            patch_plan_id=patch_plan.patch_plan_id,
            fix_attempt_id=regression_result.fix_attempt_id,
            verification_result_id=regression_result.verification_result_id,
            regression_test_id=regression_result.regression_test_id,
            verdict=execution.verdict,
            reviewer_opinions=execution.reviewer_opinions,
            synthesis_summary=execution.synthesis_summary,
            blocking_issues=execution.blocking_issues,
            diff_artifact_path=execution.diff_artifact_path,
            artifact_path=str(artifact_path),
            created_at=datetime.now(UTC),
        )
        artifact_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._peer_review_result_repository.add(result)

    def _emit_peer_review_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PEER_REVIEW_STARTED,
                stage=OrchestrationStage.PEER_REVIEW,
                agent="peer_review_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_peer_review_result_event(self, run_id: str, result: PeerReviewResult) -> None:
        event_type = {
            PeerReviewVerdict.APPROVED: AgentEventType.PEER_REVIEW_APPROVED,
            PeerReviewVerdict.CHANGES_REQUESTED: AgentEventType.PEER_REVIEW_CHANGES_REQUESTED,
            PeerReviewVerdict.REJECTED: AgentEventType.PEER_REVIEW_REJECTED,
        }[result.verdict]
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=event_type,
                stage=OrchestrationStage.PEER_REVIEW,
                agent="peer_review_agent",
                payload={
                    "peer_review_id": result.peer_review_id,
                    "patch_plan_id": result.patch_plan_id,
                    "verdict": result.verdict.value,
                    "blocking_issues": result.blocking_issues,
                },
            ),
        )
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PEER_REVIEW_COMPLETED,
                stage=OrchestrationStage.PEER_REVIEW,
                agent="peer_review_agent",
                payload={
                    "peer_review_id": result.peer_review_id,
                    "patch_plan_id": result.patch_plan_id,
                    "verdict": result.verdict.value,
                },
            ),
        )

    @staticmethod
    def _resolve_run_status(results: list[PeerReviewResult]) -> RunStatus:
        if not results:
            return RunStatus.PEER_REVIEW
        if any(result.verdict == PeerReviewVerdict.REJECTED for result in results):
            return RunStatus.FAILED
        if any(result.verdict == PeerReviewVerdict.CHANGES_REQUESTED for result in results):
            return RunStatus.AWAITING_APPROVAL
        return RunStatus.FINAL_REVIEW

    def _write_peer_review_results_artifact(self, baseline_dir: Path, run_id: str) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / PEER_REVIEW_RESULTS_ARTIFACT_NAME
        results = self._peer_review_result_repository.list_by_run(run_id)
        payload = [result.model_dump(mode="json") for result in results]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path


def _latest_regression_by_plan(
    regression_results: list[RegressionTestResult],
) -> dict[str, RegressionTestResult]:
    latest: dict[str, RegressionTestResult] = {}
    for result in regression_results:
        existing = latest.get(result.patch_plan_id)
        if existing is None or result.created_at > existing.created_at:
            latest[result.patch_plan_id] = result
    return latest


def _completed_regression_targets(
    regression_results: list[RegressionTestResult],
) -> dict[str, RegressionTestResult]:
    latest_by_plan = _latest_regression_by_plan(regression_results)
    return {
        patch_plan_id: result
        for patch_plan_id, result in latest_by_plan.items()
        if result.status in {RegressionTestStatus.PASSED, RegressionTestStatus.SKIPPED}
    }
