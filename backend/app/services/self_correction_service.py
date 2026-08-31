import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.self_correction_agent import SelfCorrectionAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.fixing.applicator import FixApplicator
from app.adk.fixing.llm_rewriter import GeminiCodeRewriter
from app.adk.self_correction.engine import SelfCorrectionRunResult
from app.adk.verification.engine import VerificationEngine
from app.adk.workflows.stages import OrchestrationStage
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.risk_decision_repository import RiskDecisionRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.self_correction_cycle_repository import (
    SelfCorrectionCycleNotFoundError,
    SelfCorrectionCycleRepository,
)
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.agent_event import AgentEventType
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import PatchPlan
from app.models.run import RunStatus
from app.models.self_correction_cycle import SelfCorrectionCycle
from app.models.self_correction_enums import SelfCorrectionStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.scanners import SubprocessCommandRunner
from app.schemas.self_correction import RunSelfCorrectionResponse, SelfCorrectionCycleResponse
from app.services.code_fix_service import FIX_ATTEMPTS_ARTIFACT_NAME
from app.services.gemini_credential_service import GeminiCredentialService
from app.services.run_service import RunService
from app.services.verification_service import VERIFICATION_RESULTS_ARTIFACT_NAME

logger = get_logger(__name__)

SELF_CORRECTION_CYCLES_ARTIFACT_NAME = "self_correction_cycles.json"


class VerificationFailuresRequiredError(Exception):
    def __init__(
        self,
        message: str = "Failed verification results are required for self-correction",
    ) -> None:
        self.message = message
        super().__init__(message)


class SelfCorrectionService:
    """Retry autonomous fixes when verification fails, up to a configured limit."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        risk_decision_repository: RiskDecisionRepository,
        fix_attempt_repository: FixAttemptRepository,
        verification_result_repository: VerificationResultRepository,
        self_correction_cycle_repository: SelfCorrectionCycleRepository,
        event_repository: AgentEventRepository,
        self_correction_agent: SelfCorrectionAgent | None = None,
        command_runner: SubprocessCommandRunner | None = None,
        scanner_timeout_seconds: int = 120,
        max_fix_iterations: int = 3,
        settings: Settings | None = None,
        gemini_credential_service: GeminiCredentialService | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._risk_decision_repository = risk_decision_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._verification_result_repository = verification_result_repository
        self._self_correction_cycle_repository = self_correction_cycle_repository
        self._event_repository = event_repository
        self._self_correction_agent = self_correction_agent or SelfCorrectionAgent()
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._scanner_timeout_seconds = scanner_timeout_seconds
        self._max_fix_iterations = max_fix_iterations
        self._settings = settings
        self._gemini_credential_service = gemini_credential_service

    def correct_run(self, user_id: str, run_id: str) -> RunSelfCorrectionResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        verification_results = self._verification_result_repository.list_by_run(run_id)
        failed_targets = _failed_verification_targets(verification_results)
        if not failed_targets:
            raise VerificationFailuresRequiredError()

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        plans_by_id = {plan.patch_plan_id: plan for plan in patch_plans}
        risk_by_plan = {
            decision.patch_plan_id: decision
            for decision in self._risk_decision_repository.list_by_run(run_id)
        }
        fix_attempts_by_plan = _latest_fix_attempts_by_plan(
            self._fix_attempt_repository.list_by_run(run_id),
        )
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)

        api_key = None
        if self._gemini_credential_service is not None:
            api_key = self._gemini_credential_service.try_get_api_key(user_id)
        applicator = FixApplicator(
            self._command_runner,
            self._scanner_timeout_seconds,
            code_rewriter=(
                GeminiCodeRewriter(self._settings, api_key=api_key) if self._settings else None
            ),
        )
        verification_engine = VerificationEngine(
            self._command_runner,
            self._scanner_timeout_seconds,
        )

        self._run_repository.update_status(run_id, user_id, RunStatus.SELF_CORRECTING)
        self._emit_self_correction_started(run_id)

        started_at = datetime.now(UTC)
        persisted_cycles: list[SelfCorrectionCycle] = []

        for patch_plan_id, prior_verification in failed_targets.items():
            patch_plan = plans_by_id.get(patch_plan_id)
            prior_fix_attempt = fix_attempts_by_plan.get(patch_plan_id)
            risk_decision = risk_by_plan.get(patch_plan_id)
            if patch_plan is None or prior_fix_attempt is None or risk_decision is None:
                continue

            attempt_count = self._fix_attempt_repository.count_by_patch_plan(run_id, patch_plan_id)
            iteration_number = attempt_count + 1
            if attempt_count >= self._max_fix_iterations:
                cycle = self._persist_exhausted_cycle(
                    run_id,
                    patch_plan_id,
                    iteration_number,
                    prior_fix_attempt,
                    prior_verification,
                )
                persisted_cycles.append(cycle)
                continue

            execution = self._self_correction_agent.run(
                workspace,
                patch_plan,
                risk_decision,
                prior_fix_attempt,
                prior_verification,
                applicator,
                verification_engine,
            )
            cycle = self._persist_cycle(
                run_id,
                patch_plan,
                prior_fix_attempt,
                prior_verification,
                iteration_number,
                execution,
                workspace.baseline,
            )
            persisted_cycles.append(cycle)
            self._emit_patch_applied_if_needed(run_id, patch_plan, cycle)

        self._refresh_artifacts(workspace.baseline, run_id)
        all_cycles = self._self_correction_cycle_repository.list_by_run(run_id)
        self._write_self_correction_artifact(workspace.baseline, all_cycles)
        next_status = self._resolve_run_status(persisted_cycles, run_id)
        self._run_repository.update_status(run_id, user_id, next_status)
        self._emit_self_correction_completed(run_id, persisted_cycles)

        completed_at = datetime.now(UTC)
        response = RunSelfCorrectionResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            cycles=[
                SelfCorrectionCycleResponse.model_validate(cycle.model_dump())
                for cycle in persisted_cycles
            ],
            cycle_count=len(persisted_cycles),
            passed_count=sum(
                1 for cycle in persisted_cycles if cycle.status == SelfCorrectionStatus.PASSED
            ),
            failed_count=sum(
                1 for cycle in persisted_cycles if cycle.status == SelfCorrectionStatus.FAILED
            ),
            exhausted_count=sum(
                1 for cycle in persisted_cycles if cycle.status == SelfCorrectionStatus.EXHAUSTED
            ),
            skipped_count=sum(
                1 for cycle in persisted_cycles if cycle.status == SelfCorrectionStatus.SKIPPED
            ),
            run_status=next_status.value,
        )

        logger.info(
            "Self-correction completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "cycle_count": response.cycle_count,
                "passed_count": response.passed_count,
                "exhausted_count": response.exhausted_count,
                "stage": "self_correction",
            },
        )
        return response

    def list_self_correction_cycles(
        self,
        user_id: str,
        run_id: str,
    ) -> list[SelfCorrectionCycleResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        cycles = self._self_correction_cycle_repository.list_by_run(run_id)
        return [SelfCorrectionCycleResponse.model_validate(cycle.model_dump()) for cycle in cycles]

    def get_self_correction_cycle(
        self,
        user_id: str,
        run_id: str,
        self_correction_cycle_id: str,
    ) -> SelfCorrectionCycleResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        cycle = self._self_correction_cycle_repository.get_by_id_for_run(
            self_correction_cycle_id,
            run_id,
        )
        if cycle is None:
            raise SelfCorrectionCycleNotFoundError(self_correction_cycle_id)

        return SelfCorrectionCycleResponse.model_validate(cycle.model_dump())

    def _persist_exhausted_cycle(
        self,
        run_id: str,
        patch_plan_id: str,
        iteration_number: int,
        prior_fix_attempt: FixAttempt,
        prior_verification: VerificationResult,
    ) -> SelfCorrectionCycle:
        cycle = SelfCorrectionCycle(
            self_correction_cycle_id=str(ObjectId()),
            run_id=run_id,
            patch_plan_id=patch_plan_id,
            iteration_number=iteration_number,
            prior_fix_attempt_id=prior_fix_attempt.fix_attempt_id,
            prior_verification_result_id=prior_verification.verification_result_id,
            root_cause=prior_verification.failure_summary or "Maximum fix iterations reached",
            failure_summary=prior_verification.failure_summary or "Maximum fix iterations reached",
            rollback_applied=False,
            status=SelfCorrectionStatus.EXHAUSTED,
            error_message=(
                f"Maximum fix iterations ({self._max_fix_iterations}) reached for patch plan"
            ),
            created_at=datetime.now(UTC),
        )
        return self._self_correction_cycle_repository.add(cycle)

    def _persist_cycle(
        self,
        run_id: str,
        patch_plan: PatchPlan,
        prior_fix_attempt: FixAttempt,
        prior_verification: VerificationResult,
        iteration_number: int,
        execution: SelfCorrectionRunResult,
        baseline_dir: Path,
    ) -> SelfCorrectionCycle:
        retry_fix_attempt_id: str | None = None
        retry_verification_result_id: str | None = None
        error_message: str | None = None

        if execution.fix_execution is not None and execution.status != SelfCorrectionStatus.SKIPPED:
            fix_attempt = self._persist_fix_attempt(run_id, patch_plan, execution.fix_execution)
            retry_fix_attempt_id = fix_attempt.fix_attempt_id
            if execution.fix_execution.status != FixAttemptStatus.APPLIED:
                error_message = execution.fix_execution.error_message

        if (
            execution.verification_execution is not None
            and retry_fix_attempt_id is not None
            and execution.fix_execution is not None
            and execution.fix_execution.status == FixAttemptStatus.APPLIED
        ):
            fix_attempt = self._fix_attempt_repository.get_by_id_for_run(
                retry_fix_attempt_id,
                run_id,
            )
            if fix_attempt is not None:
                verification_result = self._persist_verification_result(
                    run_id,
                    fix_attempt,
                    patch_plan,
                    execution.verification_execution,
                    baseline_dir,
                )
                retry_verification_result_id = verification_result.verification_result_id

        cycle = SelfCorrectionCycle(
            self_correction_cycle_id=str(ObjectId()),
            run_id=run_id,
            patch_plan_id=patch_plan.patch_plan_id,
            iteration_number=iteration_number,
            prior_fix_attempt_id=prior_fix_attempt.fix_attempt_id,
            prior_verification_result_id=prior_verification.verification_result_id,
            root_cause=execution.root_cause,
            failure_summary=execution.failure_summary,
            rollback_applied=execution.rollback_applied,
            retry_fix_attempt_id=retry_fix_attempt_id,
            retry_verification_result_id=retry_verification_result_id,
            status=execution.status,
            error_message=error_message,
            created_at=datetime.now(UTC),
        )
        artifact_dir = baseline_dir / "self_correction" / cycle.self_correction_cycle_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "cycle.json").write_text(
            json.dumps(cycle.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._self_correction_cycle_repository.add(cycle)

    def _persist_fix_attempt(
        self,
        run_id: str,
        patch_plan: PatchPlan,
        execution,
    ) -> FixAttempt:
        attempt_number = (
            self._fix_attempt_repository.count_by_patch_plan(run_id, patch_plan.patch_plan_id) + 1
        )
        fix_attempt = FixAttempt(
            fix_attempt_id=str(ObjectId()),
            run_id=run_id,
            patch_plan_id=patch_plan.patch_plan_id,
            attempt_number=attempt_number,
            status=execution.status,
            planned_files=execution.planned_files,
            changed_files=execution.changed_files,
            unexpected_files=execution.unexpected_files,
            scope_violation=execution.scope_violation,
            backup_path=execution.backup_path,
            diff_artifact_path=execution.diff_artifact_path,
            error_message=execution.error_message,
            created_at=datetime.now(UTC),
        )
        return self._fix_attempt_repository.add(fix_attempt)

    def _persist_verification_result(
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

    def _refresh_artifacts(self, baseline_dir: Path, run_id: str) -> None:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        fix_attempts = self._fix_attempt_repository.list_by_run(run_id)
        (baseline_dir / FIX_ATTEMPTS_ARTIFACT_NAME).write_text(
            json.dumps([attempt.model_dump(mode="json") for attempt in fix_attempts], indent=2),
            encoding="utf-8",
        )
        verification_results = self._verification_result_repository.list_by_run(run_id)
        (baseline_dir / VERIFICATION_RESULTS_ARTIFACT_NAME).write_text(
            json.dumps(
                [result.model_dump(mode="json") for result in verification_results],
                indent=2,
            ),
            encoding="utf-8",
        )

    def _emit_self_correction_started(self, run_id: str) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.SELF_CORRECTION_STARTED,
                stage=OrchestrationStage.SELF_CORRECTION,
                agent="self_correction_agent",
                payload={"run_id": run_id},
            ),
        )

    def _emit_self_correction_completed(
        self,
        run_id: str,
        cycles: list[SelfCorrectionCycle],
    ) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.SELF_CORRECTION_COMPLETED,
                stage=OrchestrationStage.SELF_CORRECTION,
                agent="self_correction_agent",
                payload={
                    "cycle_count": len(cycles),
                    "passed_count": sum(
                        1 for cycle in cycles if cycle.status == SelfCorrectionStatus.PASSED
                    ),
                    "exhausted_count": sum(
                        1 for cycle in cycles if cycle.status == SelfCorrectionStatus.EXHAUSTED
                    ),
                },
            ),
        )

    def _emit_patch_applied_if_needed(
        self,
        run_id: str,
        patch_plan: PatchPlan,
        cycle: SelfCorrectionCycle,
    ) -> None:
        if cycle.status != SelfCorrectionStatus.PASSED or cycle.retry_fix_attempt_id is None:
            return

        fix_attempt = self._fix_attempt_repository.get_by_id_for_run(
            cycle.retry_fix_attempt_id,
            run_id,
        )
        if fix_attempt is None:
            return

        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PATCH_APPLIED,
                stage=OrchestrationStage.SELF_CORRECTION,
                agent="self_correction_agent",
                payload={
                    "fix_attempt_id": fix_attempt.fix_attempt_id,
                    "patch_plan_id": patch_plan.patch_plan_id,
                    "changed_files": fix_attempt.changed_files,
                    "diff_artifact_path": fix_attempt.diff_artifact_path,
                    "self_correction_cycle_id": cycle.self_correction_cycle_id,
                },
            ),
        )

    def _resolve_run_status(
        self,
        cycles: list[SelfCorrectionCycle],
        run_id: str,
    ) -> RunStatus:
        if any(cycle.status == SelfCorrectionStatus.EXHAUSTED for cycle in cycles):
            return RunStatus.AWAITING_APPROVAL

        latest_results = list(self._verification_result_repository.list_by_run(run_id))
        latest_by_plan = _latest_verification_by_plan(latest_results)
        applicable = [
            result
            for result in latest_by_plan.values()
            if result.status != VerificationStatus.SKIPPED
        ]
        if not applicable:
            return RunStatus.SELF_CORRECTING

        failed_statuses = {VerificationStatus.FAILED, VerificationStatus.ERROR}
        if any(result.status in failed_statuses for result in applicable):
            remaining = any(
                self._fix_attempt_repository.count_by_patch_plan(run_id, patch_plan_id)
                < self._max_fix_iterations
                for patch_plan_id in latest_by_plan
                if latest_by_plan[patch_plan_id].status
                in {VerificationStatus.FAILED, VerificationStatus.ERROR}
            )
            return RunStatus.SELF_CORRECTING if remaining else RunStatus.AWAITING_APPROVAL

        return RunStatus.VERIFYING

    @staticmethod
    def _write_self_correction_artifact(
        baseline_dir: Path,
        cycles: list[SelfCorrectionCycle],
    ) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / SELF_CORRECTION_CYCLES_ARTIFACT_NAME
        payload = [cycle.model_dump(mode="json") for cycle in cycles]
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


def _failed_verification_targets(
    verification_results: list[VerificationResult],
) -> dict[str, VerificationResult]:
    latest_by_plan = _latest_verification_by_plan(verification_results)
    return {
        patch_plan_id: result
        for patch_plan_id, result in latest_by_plan.items()
        if result.status in {VerificationStatus.FAILED, VerificationStatus.ERROR}
    }


def _latest_fix_attempts_by_plan(fix_attempts: list[FixAttempt]) -> dict[str, FixAttempt]:
    latest: dict[str, FixAttempt] = {}
    for attempt in fix_attempts:
        existing = latest.get(attempt.patch_plan_id)
        if existing is None or attempt.attempt_number > existing.attempt_number:
            latest[attempt.patch_plan_id] = attempt
    return latest
