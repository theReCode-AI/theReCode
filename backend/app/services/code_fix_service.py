import json
from datetime import UTC, datetime
from pathlib import Path

from bson import ObjectId

from app.adk.agents.code_fix_agent import CodeFixAgent
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.fixing.applicator import FixApplicator
from app.adk.fixing.llm_rewriter import CodeRewriter, GeminiCodeRewriter
from app.adk.workflows.stages import OrchestrationStage
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.approval_repository import ApprovalRepository
from app.db.repositories.fix_attempt_repository import (
    FixAttemptNotFoundError,
    FixAttemptRepository,
)
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.risk_decision_repository import RiskDecisionRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.models.agent_event import AgentEventType
from app.models.approval_enums import ApprovalStatus, ApprovalTrigger
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import PatchPlan
from app.models.run import RunStatus
from app.scanners import SubprocessCommandRunner
from app.schemas.fix_attempt import CodeFixResponse, FixAttemptDiffResponse, FixAttemptResponse
from app.services.gemini_credential_service import GeminiCredentialService
from app.services.risk_assessment_service import RISK_DECISIONS_ARTIFACT_NAME
from app.services.run_service import RunService
from app.workspace.artifact_reader import (
    WorkspaceArtifactAccessError,
    WorkspaceArtifactNotFoundError,
    read_workspace_text_file,
)

logger = get_logger(__name__)

FIX_ATTEMPTS_ARTIFACT_NAME = "fix_attempts.json"


class FixAttemptDiffNotFoundError(Exception):
    def __init__(self, fix_attempt_id: str) -> None:
        self.fix_attempt_id = fix_attempt_id
        super().__init__(f"Diff artifact is not available for fix attempt: {fix_attempt_id}")


def _read_diff_artifact(workspace_root: Path, artifact_path: str, fix_attempt_id: str) -> str:
    try:
        return read_workspace_text_file(workspace_root, artifact_path)
    except (WorkspaceArtifactNotFoundError, WorkspaceArtifactAccessError) as exc:
        raise FixAttemptDiffNotFoundError(fix_attempt_id) from exc


class RiskDecisionsRequiredError(Exception):
    def __init__(
        self,
        message: str = "Risk decisions must be created before applying fixes",
    ) -> None:
        self.message = message
        super().__init__(message)


class CodeFixService:
    """Apply autonomous code fixes for eligible patch plans."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        risk_decision_repository: RiskDecisionRepository,
        fix_attempt_repository: FixAttemptRepository,
        event_repository: AgentEventRepository,
        approval_repository: ApprovalRepository | None = None,
        code_fix_agent: CodeFixAgent | None = None,
        command_runner: SubprocessCommandRunner | None = None,
        scanner_timeout_seconds: int = 120,
        settings: Settings | None = None,
        code_rewriter: CodeRewriter | None = None,
        gemini_credential_service: GeminiCredentialService | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._risk_decision_repository = risk_decision_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._event_repository = event_repository
        self._approval_repository = approval_repository
        self._code_fix_agent = code_fix_agent or CodeFixAgent()
        self._command_runner = command_runner or SubprocessCommandRunner()
        self._scanner_timeout_seconds = scanner_timeout_seconds
        self._settings = settings
        self._code_rewriter = code_rewriter
        self._gemini_credential_service = gemini_credential_service

    def fix_run(self, user_id: str, run_id: str, *, force: bool = False) -> CodeFixResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        patch_plans = self._fix_plan_repository.list_by_run(run_id)
        risk_decisions = self._risk_decision_repository.list_by_run(run_id)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        risk_artifact = workspace.baseline / RISK_DECISIONS_ARTIFACT_NAME
        if not risk_decisions and not risk_artifact.is_file():
            raise RiskDecisionsRequiredError()

        risk_by_plan = {decision.patch_plan_id: decision for decision in risk_decisions}
        applicator = FixApplicator(
            self._command_runner,
            self._scanner_timeout_seconds,
            code_rewriter=self._resolve_code_rewriter(user_id),
        )

        self._run_repository.update_status(run_id, user_id, RunStatus.FIXING)
        started_at = datetime.now(UTC)
        persisted_attempts: list[FixAttempt] = []

        for patch_plan in patch_plans:
            risk_decision = risk_by_plan.get(patch_plan.patch_plan_id)
            if risk_decision is None:
                continue

            execution = self._code_fix_agent.run(
                workspace,
                patch_plan,
                risk_decision,
                applicator,
                risk_gate_approved=self._is_risk_gate_approved(run_id, patch_plan.patch_plan_id),
                force_apply=force,
            )
            attempt = self._persist_attempt(run_id, patch_plan, execution)
            persisted_attempts.append(attempt)
            self._emit_fix_event(run_id, patch_plan, attempt)

        self._write_fix_attempts_artifact(workspace.baseline, persisted_attempts)

        applied_count = sum(
            1 for attempt in persisted_attempts if attempt.status == FixAttemptStatus.APPLIED
        )
        # Standalone /fix (e.g. Retry) must not leave the run stuck in FIXING forever.
        # When nothing was applied there is no verify/review stage to continue into.
        next_status = RunStatus.FIXING if applied_count > 0 else RunStatus.COMPLETED
        self._run_repository.update_status(run_id, user_id, next_status)

        completed_at = datetime.now(UTC)
        response = CodeFixResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            fix_attempts=[
                FixAttemptResponse.model_validate(attempt.model_dump())
                for attempt in persisted_attempts
            ],
            attempt_count=len(persisted_attempts),
            applied_count=applied_count,
            skipped_count=sum(
                1 for attempt in persisted_attempts if attempt.status == FixAttemptStatus.SKIPPED
            ),
            failed_count=sum(
                1 for attempt in persisted_attempts if attempt.status == FixAttemptStatus.FAILED
            ),
            rolled_back_count=sum(
                1
                for attempt in persisted_attempts
                if attempt.status == FixAttemptStatus.ROLLED_BACK
            ),
            run_status=next_status.value,
        )

        logger.info(
            "Code fix execution completed",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "attempt_count": response.attempt_count,
                "applied_count": response.applied_count,
                "stage": "code_fixing",
            },
        )
        return response

    def list_fix_attempts(self, user_id: str, run_id: str) -> list[FixAttemptResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        fix_attempts = self._fix_attempt_repository.list_by_run(run_id)
        return [
            FixAttemptResponse.model_validate(attempt.model_dump()) for attempt in fix_attempts
        ]

    def get_fix_attempt(
        self,
        user_id: str,
        run_id: str,
        fix_attempt_id: str,
    ) -> FixAttemptResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        fix_attempt = self._fix_attempt_repository.get_by_id_for_run(fix_attempt_id, run_id)
        if fix_attempt is None:
            raise FixAttemptNotFoundError(fix_attempt_id)

        return FixAttemptResponse.model_validate(fix_attempt.model_dump())

    def get_fix_attempt_diff(
        self,
        user_id: str,
        run_id: str,
        fix_attempt_id: str,
    ) -> FixAttemptDiffResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        fix_attempt = self._fix_attempt_repository.get_by_id_for_run(fix_attempt_id, run_id)
        if fix_attempt is None:
            raise FixAttemptNotFoundError(fix_attempt_id)
        if not fix_attempt.diff_artifact_path:
            raise FixAttemptDiffNotFoundError(fix_attempt_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        content = _read_diff_artifact(
            workspace.root,
            fix_attempt.diff_artifact_path,
            fix_attempt.fix_attempt_id,
        )

        return FixAttemptDiffResponse(
            fix_attempt_id=fix_attempt.fix_attempt_id,
            run_id=run_id,
            diff_path=fix_attempt.diff_artifact_path,
            content=content,
            changed_files=fix_attempt.changed_files,
        )

    def _persist_attempt(
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

    def _is_risk_gate_approved(self, run_id: str, patch_plan_id: str) -> bool:
        if self._approval_repository is None:
            return False

        for approval in self._approval_repository.list_by_run(run_id):
            if (
                approval.trigger == ApprovalTrigger.RISK_GATE
                and approval.patch_plan_id == patch_plan_id
                and approval.status == ApprovalStatus.APPROVED
            ):
                return True
        return False

    def _resolve_code_rewriter(self, user_id: str) -> CodeRewriter | None:
        if self._code_rewriter is not None:
            return self._code_rewriter
        if self._settings is None:
            return None
        api_key = None
        if self._gemini_credential_service is not None:
            api_key = self._gemini_credential_service.try_get_api_key(user_id)
        return GeminiCodeRewriter(self._settings, api_key=api_key)

    def _emit_fix_event(self, run_id: str, patch_plan: PatchPlan, attempt: FixAttempt) -> None:
        if attempt.status != FixAttemptStatus.APPLIED:
            return

        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.PATCH_APPLIED,
                stage=OrchestrationStage.CODE_FIXING,
                agent="code_fix_agent",
                payload={
                    "fix_attempt_id": attempt.fix_attempt_id,
                    "patch_plan_id": patch_plan.patch_plan_id,
                    "changed_files": attempt.changed_files,
                    "diff_artifact_path": attempt.diff_artifact_path,
                },
            ),
        )

    @staticmethod
    def _write_fix_attempts_artifact(
        baseline_dir: Path,
        fix_attempts: list[FixAttempt],
    ) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / FIX_ATTEMPTS_ARTIFACT_NAME
        payload = [attempt.model_dump(mode="json") for attempt in fix_attempts]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path
