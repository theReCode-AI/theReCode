import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.verification_agent import VerificationAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.verification.engine import VerificationEngine
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.verification_result_repository import (
    VerificationResultNotFoundError,
    VerificationResultRepository,
)
from app.models.agent_event import AgentEventType
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.run import RunStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.scanners import SubprocessCommandRunner
from app.schemas.verification_result import RunVerificationResponse, VerificationResultResponse
from app.services.code_fix_service import FIX_ATTEMPTS_ARTIFACT_NAME
from app.services.run_service import RunService

logger = get_logger(__name__)

VERIFICATION_RESULTS_ARTIFACT_NAME = "verification_results.json"


class FixAttemptsRequiredError(Exception):
    def __init__(
        self,
        message: str = "Fix attempts must be created before verification",
    ) -> None:
        self.message = message
        super().__init__(message)


class VerificationService:
    """Verify applied fixes using patch-plan tests and targeted scanners."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        fix_attempt_repository: FixAttemptRepository,
        verification_result_repository: VerificationResultRepository,
        event_repository: AgentEventRepository,
        verification_agent: VerificationAgent | None = None,
        command_runner: SubprocessCommandRunner | None = None,
        scanner_timeout_seconds: int = 120,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._verification_result_repository = verification_result_repository
        self._event_repository = event_repository
        self._verification_agent = verification_agent or VerificationAgent()
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._scanner_timeout_seconds = scanner_timeout_seconds

    def verify_run(self, user_id: str, run_id: str) -> RunVerificationResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        fix_attempts = self._fix_attempt_repository.list_by_run(run_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        fix_attempts_artifact = workspace.baseline / FIX_ATTEMPTS_ARTIFACT_NAME
        if not fix_attempts and not fix_attempts_artifact.is_file():
            raise FixAttemptsRequiredError()

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        plans_by_id = {plan.patch_plan_id: plan for plan in patch_plans}
        engine = VerificationEngine(self._command_runner, self._scanner_timeout_seconds)

        self._run_repository.update_status(run_id, user_id, RunStatus.VERIFYING)
        self._emit_verification_started(run_id)

        started_at = datetime.now(UTC)
        persisted_results: list[VerificationResult] = []

        for fix_attempt in fix_attempts:
            patch_plan = plans_by_id.get(fix_attempt.patch_plan_id)
            if patch_plan is None:
                continue

            execution = self._verification_agent.run(
                workspace.working,
                patch_plan,
                fix_attempt,
                engine,
            )
            result = self._persist_result(
                run_id,
                fix_attempt,
                patch_plan,
                execution,
                workspace.baseline,
            )
            persisted_results.append(result)
            self._emit_verification_result_event(run_id, result)

        self._write_verification_results_artifact(workspace.baseline, persisted_results)
        next_status = self._resolve_run_status(persisted_results)
        self._run_repository.update_status(run_id, user_id, next_status)

        completed_at = datetime.now(UTC)
        response = RunVerificationResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            verification_results=[
                VerificationResultResponse.model_validate(result.model_dump())
                for result in persisted_results
            ],
            result_count=len(persisted_results),
            passed_count=sum(
                1 for result in persisted_results if result.status == VerificationStatus.PASSED
            ),
            failed_count=sum(
                1 for result in persisted_results if result.status == VerificationStatus.FAILED
            ),
            skipped_count=sum(
                1 for result in persisted_results if result.status == VerificationStatus.SKIPPED
            ),
            error_count=sum(
                1 for result in persisted_results if result.status == VerificationStatus.ERROR
            ),
            run_status=next_status.value,
        )

        logger.info(
            "Verification completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "result_count": response.result_count,
                "passed_count": response.passed_count,
                "failed_count": response.failed_count,
                "stage": "verification",
            },
        )
        return response

    def list_verification_results(
        self,
        user_id: str,
        run_id: str,
    ) -> list[VerificationResultResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        results = self._verification_result_repository.list_by_run(run_id)
        return [
            VerificationResultResponse.model_validate(result.model_dump()) for result in results
        ]

    def get_verification_result(
        self,
        user_id: str,
        run_id: str,
        verification_result_id: str,
    ) -> VerificationResultResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        result = self._verification_result_repository.get_by_id_for_run(
            verification_result_id,
            run_id,
        )
        if result is None:
            raise VerificationResultNotFoundError(verification_result_id)

        return VerificationResultResponse.model_validate(result.model_dump())

    def _persist_result(
        self,
        run_id: str,
        fix_attempt: FixAttempt,
        patch_plan: PatchPlan,
        execution,
        baseline_dir: Path,
    ) -> VerificationResult:
        artifact_dir = baseline_dir / "verification" / fix_attempt.fix_attempt_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "result.json"

        verification_result = VerificationResult(
            verification_result_id=str(ObjectId()),
            run_id=run_id,
            fix_attempt_id=fix_attempt.fix_attempt_id,
            patch_plan_id=patch_plan.patch_plan_id,
            status=execution.status,
            checks=execution.checks,
            passed_checks=execution.passed_checks,
            failed_checks=execution.failed_checks,
            skipped_checks=execution.skipped_checks,
            failure_summary=execution.failure_summary,
            artifact_path=str(artifact_path),
            created_at=datetime.now(UTC),
        )
        artifact_path.write_text(
            json.dumps(verification_result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._verification_result_repository.add(verification_result)

    def _emit_verification_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.VERIFICATION_STARTED,
                stage=OrchestrationStage.VERIFICATION,
                agent="verification_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_verification_result_event(
        self,
        run_id: str,
        result: VerificationResult,
    ) -> None:
        if result.status == VerificationStatus.SKIPPED:
            return

        event_type = (
            AgentEventType.VERIFICATION_PASSED
            if result.status == VerificationStatus.PASSED
            else AgentEventType.VERIFICATION_FAILED
        )
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=event_type,
                stage=OrchestrationStage.VERIFICATION,
                agent="verification_agent",
                payload={
                    "verification_result_id": result.verification_result_id,
                    "fix_attempt_id": result.fix_attempt_id,
                    "patch_plan_id": result.patch_plan_id,
                    "status": result.status.value,
                    "failed_checks": result.failed_checks,
                    "failure_summary": result.failure_summary,
                },
            ),
        )

    @staticmethod
    def _resolve_run_status(results: list[VerificationResult]) -> RunStatus:
        applicable = [
            result
            for result in results
            if result.status != VerificationStatus.SKIPPED
        ]
        if not applicable:
            return RunStatus.VERIFYING
        if any(result.status == VerificationStatus.FAILED for result in applicable):
            return RunStatus.SELF_CORRECTING
        if any(result.status == VerificationStatus.ERROR for result in applicable):
            return RunStatus.SELF_CORRECTING
        return RunStatus.VERIFYING

    @staticmethod
    def _write_verification_results_artifact(
        baseline_dir: Path,
        verification_results: list[VerificationResult],
    ) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / VERIFICATION_RESULTS_ARTIFACT_NAME
        payload = [result.model_dump(mode="json") for result in verification_results]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path
