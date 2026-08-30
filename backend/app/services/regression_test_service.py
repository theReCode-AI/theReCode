import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.regression_test_agent import RegressionTestAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.regression.engine import RegressionTestEngine
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.regression_test_result_repository import (
    RegressionTestResultNotFoundError,
    RegressionTestResultRepository,
)
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.agent_event import AgentEventType
from app.models.patch_plan import PatchPlan
from app.models.regression_test_enums import RegressionTestStatus
from app.models.regression_test_result import RegressionTestResult
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.scanners import SubprocessCommandRunner
from app.schemas.regression_test import RegressionTestResultResponse, RunRegressionTestResponse
from app.services.run_service import RunService
from app.services.verification_service import VERIFICATION_RESULTS_ARTIFACT_NAME

logger = get_logger(__name__)

REGRESSION_TEST_RESULTS_ARTIFACT_NAME = "regression_test_results.json"


class PassedVerificationsRequiredError(Exception):
    def __init__(
        self,
        message: str = "Passed verification results are required before regression testing",
    ) -> None:
        self.message = message
        super().__init__(message)


class RegressionTestService:
    """Generate and run regression tests for verified meaningful fixes."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        verification_result_repository: VerificationResultRepository,
        regression_test_result_repository: RegressionTestResultRepository,
        event_repository: AgentEventRepository,
        regression_test_agent: RegressionTestAgent | None = None,
        command_runner: SubprocessCommandRunner | None = None,
        scanner_timeout_seconds: int = 120,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._verification_result_repository = verification_result_repository
        self._regression_test_result_repository = regression_test_result_repository
        self._event_repository = event_repository
        self._regression_test_agent = regression_test_agent or RegressionTestAgent()
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._scanner_timeout_seconds = scanner_timeout_seconds

    def run_regression_tests(self, user_id: str, run_id: str) -> RunRegressionTestResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        verification_results = self._verification_result_repository.list_by_run(run_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        verification_artifact = workspace.baseline / VERIFICATION_RESULTS_ARTIFACT_NAME
        passed_targets = _passed_verification_targets(verification_results)
        if not passed_targets and not verification_artifact.is_file():
            raise PassedVerificationsRequiredError()
        if not passed_targets:
            raise PassedVerificationsRequiredError()

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        plans_by_id = {plan.patch_plan_id: plan for plan in patch_plans}
        engine = RegressionTestEngine(self._command_runner, self._scanner_timeout_seconds)

        self._emit_regression_started(run_id)
        started_at = datetime.now(UTC)
        persisted_results: list[RegressionTestResult] = []

        for patch_plan_id, verification_result in passed_targets.items():
            patch_plan = plans_by_id.get(patch_plan_id)
            if patch_plan is None:
                continue

            output_dir = workspace.baseline / "regression" / patch_plan_id
            execution = self._regression_test_agent.run(
                workspace.working,
                patch_plan,
                output_dir,
                engine,
            )
            result = self._persist_result(
                run_id,
                patch_plan,
                verification_result,
                execution,
                output_dir,
            )
            persisted_results.append(result)
            self._emit_regression_result_event(run_id, result)

        self._write_regression_results_artifact(workspace.baseline, run_id)
        next_status = self._resolve_run_status(persisted_results)
        self._run_repository.update_status(run_id, user_id, next_status)

        completed_at = datetime.now(UTC)
        response = RunRegressionTestResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            regression_tests=[
                RegressionTestResultResponse.model_validate(result.model_dump())
                for result in persisted_results
            ],
            result_count=len(persisted_results),
            passed_count=sum(
                1 for result in persisted_results if result.status == RegressionTestStatus.PASSED
            ),
            failed_count=sum(
                1 for result in persisted_results if result.status == RegressionTestStatus.FAILED
            ),
            skipped_count=sum(
                1 for result in persisted_results if result.status == RegressionTestStatus.SKIPPED
            ),
            error_count=sum(
                1 for result in persisted_results if result.status == RegressionTestStatus.ERROR
            ),
            run_status=next_status.value,
        )

        logger.info(
            "Regression testing completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "result_count": response.result_count,
                "passed_count": response.passed_count,
                "failed_count": response.failed_count,
                "stage": "regression_testing",
            },
        )
        return response

    def list_regression_tests(
        self,
        user_id: str,
        run_id: str,
    ) -> list[RegressionTestResultResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        results = self._regression_test_result_repository.list_by_run(run_id)
        return [
            RegressionTestResultResponse.model_validate(result.model_dump()) for result in results
        ]

    def get_regression_test(
        self,
        user_id: str,
        run_id: str,
        regression_test_id: str,
    ) -> RegressionTestResultResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        result = self._regression_test_result_repository.get_by_id_for_run(
            regression_test_id,
            run_id,
        )
        if result is None:
            raise RegressionTestResultNotFoundError(regression_test_id)

        return RegressionTestResultResponse.model_validate(result.model_dump())

    def _persist_result(
        self,
        run_id: str,
        patch_plan: PatchPlan,
        verification_result: VerificationResult,
        execution,
        output_dir: Path,
    ) -> RegressionTestResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "result.json"

        result = RegressionTestResult(
            regression_test_id=str(ObjectId()),
            run_id=run_id,
            patch_plan_id=patch_plan.patch_plan_id,
            fix_attempt_id=verification_result.fix_attempt_id,
            verification_result_id=verification_result.verification_result_id,
            status=execution.status,
            eligible=execution.eligible,
            test_file_path=execution.test_file_path,
            targeted_exit_code=execution.targeted_exit_code,
            targeted_tests=execution.targeted_tests,
            targeted_passed=execution.targeted_passed,
            suite_exit_code=execution.suite_exit_code,
            suite_tests=execution.suite_tests,
            suite_passed=execution.suite_passed,
            failure_summary=execution.failure_summary,
            artifact_path=str(artifact_path),
            created_at=datetime.now(UTC),
        )
        artifact_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._regression_test_result_repository.add(result)

    def _emit_regression_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.REGRESSION_TEST_STARTED,
                stage=OrchestrationStage.REGRESSION_TESTING,
                agent="regression_test_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_regression_result_event(self, run_id: str, result: RegressionTestResult) -> None:
        if result.status == RegressionTestStatus.SKIPPED:
            return

        event_type = (
            AgentEventType.REGRESSION_TEST_PASSED
            if result.status == RegressionTestStatus.PASSED
            else AgentEventType.REGRESSION_TEST_FAILED
        )
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=event_type,
                stage=OrchestrationStage.REGRESSION_TESTING,
                agent="regression_test_agent",
                payload={
                    "regression_test_id": result.regression_test_id,
                    "patch_plan_id": result.patch_plan_id,
                    "status": result.status.value,
                    "test_file_path": result.test_file_path,
                    "failure_summary": result.failure_summary,
                },
            ),
        )

    @staticmethod
    def _resolve_run_status(results: list[RegressionTestResult]) -> RunStatus:
        applicable = [
            result for result in results if result.status != RegressionTestStatus.SKIPPED
        ]
        if not applicable:
            return RunStatus.VERIFYING
        if any(
            result.status in {RegressionTestStatus.FAILED, RegressionTestStatus.ERROR}
            for result in applicable
        ):
            return RunStatus.FAILED
        return RunStatus.VERIFYING

    def _write_regression_results_artifact(self, baseline_dir: Path, run_id: str) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / REGRESSION_TEST_RESULTS_ARTIFACT_NAME
        results = self._regression_test_result_repository.list_by_run(run_id)
        payload = [result.model_dump(mode="json") for result in results]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path


def _latest_verification_by_plan(
    verification_results: list[VerificationResult],
) -> dict[str, VerificationResult]:
    latest: dict[str, VerificationResult] = {}
    for result in verification_results:
        existing = latest.get(result.patch_plan_id)
        if existing is None or result.created_at > existing.created_at:
            latest[result.patch_plan_id] = result
    return latest


def _passed_verification_targets(
    verification_results: list[VerificationResult],
) -> dict[str, VerificationResult]:
    latest_by_plan = _latest_verification_by_plan(verification_results)
    return {
        patch_plan_id: result
        for patch_plan_id, result in latest_by_plan.items()
        if result.status == VerificationStatus.PASSED
    }
