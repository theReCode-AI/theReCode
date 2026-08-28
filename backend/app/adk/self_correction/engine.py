"""Self-correction engine: rollback, retry fix, and re-verify."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adk.agents.code_fix_agent import CodeFixAgent, FixExecutionResult
from app.adk.agents.verification_agent import VerificationAgent
from app.adk.fixing.applicator import FixApplicator
from app.adk.fixing.backup import PatchBackupManager
from app.adk.fixing.working_copy import WorkingCopyManager
from app.adk.self_correction.failure_analyzer import FailureAnalyzer
from app.adk.verification.engine import VerificationEngine, VerificationRunResult
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.patch_plan import PatchPlan
from app.models.risk_decision import RiskDecision
from app.models.self_correction_enums import SelfCorrectionStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult
from app.workspace.models import RunWorkspace


@dataclass(frozen=True)
class SelfCorrectionRunResult:
    status: SelfCorrectionStatus
    root_cause: str
    failure_summary: str
    rollback_applied: bool
    fix_execution: FixExecutionResult | None
    verification_execution: VerificationRunResult | None


class SelfCorrectionEngine:
    """Retry an autonomous fix after verification failure."""

    def __init__(
        self,
        failure_analyzer: FailureAnalyzer | None = None,
        working_copy_manager: WorkingCopyManager | None = None,
        backup_manager: PatchBackupManager | None = None,
        code_fix_agent: CodeFixAgent | None = None,
        verification_agent: VerificationAgent | None = None,
    ) -> None:
        self._failure_analyzer = failure_analyzer or FailureAnalyzer()
        self._working_copy_manager = working_copy_manager or WorkingCopyManager()
        self._backup_manager = backup_manager or PatchBackupManager()
        self._code_fix_agent = code_fix_agent or CodeFixAgent()
        self._verification_agent = verification_agent or VerificationAgent()

    def correct(
        self,
        workspace: RunWorkspace,
        patch_plan: PatchPlan,
        risk_decision: RiskDecision,
        prior_fix_attempt: FixAttempt,
        prior_verification: VerificationResult,
        applicator: FixApplicator,
        verification_engine: VerificationEngine,
    ) -> SelfCorrectionRunResult:
        root_cause = self._failure_analyzer.analyze(prior_verification)
        failure_summary = prior_verification.failure_summary or root_cause
        rollback_applied = False

        if not risk_decision.autonomous_fix_allowed:
            return SelfCorrectionRunResult(
                status=SelfCorrectionStatus.SKIPPED,
                root_cause=root_cause,
                failure_summary=failure_summary,
                rollback_applied=False,
                fix_execution=None,
                verification_execution=None,
            )

        working_root = self._working_copy_manager.prepare(workspace)
        if prior_fix_attempt.backup_path:
            backup_root = Path(prior_fix_attempt.backup_path)
            if backup_root.is_dir():
                self._backup_manager.restore_working_tree(working_root, backup_root)
                rollback_applied = True

        fix_execution = self._code_fix_agent.run(
            workspace,
            patch_plan,
            risk_decision,
            applicator,
        )
        if fix_execution.status != FixAttemptStatus.APPLIED:
            return SelfCorrectionRunResult(
                status=SelfCorrectionStatus.FAILED,
                root_cause=root_cause,
                failure_summary=failure_summary,
                rollback_applied=rollback_applied,
                fix_execution=fix_execution,
                verification_execution=None,
            )

        retry_fix_attempt = FixAttempt(
            fix_attempt_id="pending",
            run_id=prior_fix_attempt.run_id,
            patch_plan_id=prior_fix_attempt.patch_plan_id,
            attempt_number=prior_fix_attempt.attempt_number + 1,
            status=FixAttemptStatus.APPLIED,
            planned_files=fix_execution.planned_files,
            changed_files=fix_execution.changed_files,
            unexpected_files=fix_execution.unexpected_files,
            scope_violation=fix_execution.scope_violation,
            backup_path=fix_execution.backup_path,
            diff_artifact_path=fix_execution.diff_artifact_path,
            error_message=fix_execution.error_message,
            created_at=prior_fix_attempt.created_at,
        )
        verification_execution = self._verification_agent.run(
            working_root,
            patch_plan,
            retry_fix_attempt,
            verification_engine,
        )

        if verification_execution.status == VerificationStatus.PASSED:
            status = SelfCorrectionStatus.PASSED
        else:
            status = SelfCorrectionStatus.FAILED

        return SelfCorrectionRunResult(
            status=status,
            root_cause=root_cause,
            failure_summary=failure_summary,
            rollback_applied=rollback_applied,
            fix_execution=fix_execution,
            verification_execution=verification_execution,
        )
