import json
from datetime import UTC, datetime
from pathlib import Path

from app.adk.approval.card_builder import ApprovalBuildContext, build_pending_approvals
from app.adk.events import AgentEventEmitter, WorkflowEvent
from app.adk.workflows.stages import OrchestrationStage
from app.core.logging import get_logger
from app.db.repositories.agent_event_repository import AgentEventRepository
from app.db.repositories.approval_repository import ApprovalNotFoundError, ApprovalRepository
from app.db.repositories.fix_attempt_repository import FixAttemptRepository
from app.db.repositories.fix_plan_repository import FixPlanRepository
from app.db.repositories.peer_review_result_repository import PeerReviewResultRepository
from app.db.repositories.risk_decision_repository import RiskDecisionRepository
from app.db.repositories.run_repository import RunNotFoundError, RunRepository
from app.db.repositories.self_correction_cycle_repository import SelfCorrectionCycleRepository
from app.db.repositories.verification_result_repository import VerificationResultRepository
from app.models.agent_event import AgentEventType
from app.models.approval import HumanApproval
from app.models.approval_enums import ApprovalStatus, ApprovalTrigger, HumanDecision
from app.models.fix_attempt import FixAttempt
from app.models.peer_review_result import PeerReviewResult
from app.models.run import RunStatus
from app.models.self_correction_cycle import SelfCorrectionCycle
from app.schemas.approval import (
    ApprovalDiffResponse,
    HumanApprovalResponse,
    PrepareApprovalsResponse,
    SubmitApprovalDecisionRequest,
    SubmitApprovalDecisionResponse,
)
from app.services.run_service import RunService
from app.workspace.artifact_reader import (
    WorkspaceArtifactAccessError,
    WorkspaceArtifactNotFoundError,
    read_workspace_text_file,
)

logger = get_logger(__name__)

APPROVALS_ARTIFACT_NAME = "approvals.json"
HUMAN_FEEDBACK_ARTIFACT_NAME = "human_feedback.json"


class RunNotAwaitingApprovalError(Exception):
    def __init__(
        self,
        message: str = "Run must be awaiting approval before preparing human approvals",
    ) -> None:
        self.message = message
        super().__init__(message)


class ApprovalAlreadyDecidedError(Exception):
    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id
        super().__init__(f"Approval has already been decided: {approval_id}")


class FeedbackRequiredError(Exception):
    def __init__(
        self,
        message: str = "Feedback is required when requesting changes",
    ) -> None:
        self.message = message
        super().__init__(message)


class ApprovalDiffNotFoundError(Exception):
    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id
        super().__init__(f"Diff artifact is not available for approval: {approval_id}")


class HumanApprovalService:
    """Prepare approval cards and record human approve/reject/request-changes decisions."""

    def __init__(
        self,
        run_repository: RunRepository,
        run_service: RunService,
        fix_plan_repository: FixPlanRepository,
        risk_decision_repository: RiskDecisionRepository,
        fix_attempt_repository: FixAttemptRepository,
        verification_result_repository: VerificationResultRepository,
        peer_review_result_repository: PeerReviewResultRepository,
        self_correction_cycle_repository: SelfCorrectionCycleRepository,
        approval_repository: ApprovalRepository,
        event_repository: AgentEventRepository,
    ) -> None:
        self._run_repository = run_repository
        self._run_service = run_service
        self._fix_plan_repository = fix_plan_repository
        self._risk_decision_repository = risk_decision_repository
        self._fix_attempt_repository = fix_attempt_repository
        self._verification_result_repository = verification_result_repository
        self._peer_review_result_repository = peer_review_result_repository
        self._self_correction_cycle_repository = self_correction_cycle_repository
        self._approval_repository = approval_repository
        self._event_repository = event_repository

    def prepare_approvals(self, user_id: str, run_id: str) -> PrepareApprovalsResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        started_at = datetime.now(UTC)
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        existing_approvals = self._approval_repository.list_by_run(run_id)
        context = self._build_approval_context(run_id, existing_approvals)
        new_approvals = build_pending_approvals(run_id, context)
        has_pending_approvals = any(
            approval.status == ApprovalStatus.PENDING for approval in existing_approvals
        )
        if (
            run.status != RunStatus.AWAITING_APPROVAL
            and not new_approvals
            and not has_pending_approvals
        ):
            raise RunNotAwaitingApprovalError()
        persisted_approvals = existing_approvals
        for approval in new_approvals:
            output_dir = workspace.baseline / "approvals" / approval.approval_id
            persisted = self._persist_approval(approval, output_dir)
            persisted_approvals.append(persisted)
            self._emit_approval_required(run_id, persisted)

        self._write_approvals_artifact(workspace.baseline, run_id)
        all_approvals = self._approval_repository.list_by_run(run_id)
        pending_count = sum(
            1 for approval in all_approvals if approval.status == ApprovalStatus.PENDING
        )
        if pending_count > 0 and run.status != RunStatus.AWAITING_APPROVAL:
            updated_run = self._run_repository.update_status(
                run_id,
                user_id,
                RunStatus.AWAITING_APPROVAL,
            )
            if updated_run is not None:
                run = updated_run

        completed_at = datetime.now(UTC)
        response = PrepareApprovalsResponse(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            approvals=[
                HumanApprovalResponse.model_validate(approval.model_dump())
                for approval in all_approvals
            ],
            approval_count=len(all_approvals),
            pending_count=pending_count,
            run_status=run.status.value,
        )

        logger.info(
            "Human approvals prepared",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "approval_count": response.approval_count,
                "pending_count": response.pending_count,
                "stage": "human_approval",
            },
        )
        return response

    def requires_risk_gate_approval(self, run_id: str) -> bool:
        risk_decisions = self._risk_decision_repository.list_by_run(run_id)
        return any(decision.approval_required for decision in risk_decisions)

    def has_blocking_risk_gate_approval(self, run_id: str) -> bool:
        if not self.requires_risk_gate_approval(run_id):
            return False

        approvals = self._approval_repository.list_by_run(run_id)
        risk_gate_approvals = [
            approval for approval in approvals if approval.trigger == ApprovalTrigger.RISK_GATE
        ]
        if not risk_gate_approvals:
            return True

        return any(
            approval.status == ApprovalStatus.PENDING for approval in risk_gate_approvals
        )

    def should_resume_pipeline_after_decision(
        self,
        decision: HumanDecision,
        trigger: ApprovalTrigger,
        run_status: RunStatus,
    ) -> bool:
        return (
            decision == HumanDecision.APPROVE
            and trigger == ApprovalTrigger.RISK_GATE
            and run_status == RunStatus.FIXING
        )

    def _build_approval_context(
        self,
        run_id: str,
        existing_approvals: list[HumanApproval],
    ) -> ApprovalBuildContext:
        existing_keys = {
            (approval.trigger.value, approval.patch_plan_id) for approval in existing_approvals
        }
        return ApprovalBuildContext(
            patch_plans_by_id={
                plan.patch_plan_id: plan for plan in self._fix_plan_repository.list_by_run(run_id)
            },
            risk_decisions_by_plan=_latest_risk_by_plan(
                self._risk_decision_repository.list_by_run(run_id),
            ),
            fix_attempts_by_plan=_latest_fix_attempts_by_plan(
                self._fix_attempt_repository.list_by_run(run_id),
            ),
            verifications_by_plan={
                result.verification_result_id: result
                for result in self._verification_result_repository.list_by_run(run_id)
            },
            peer_reviews_by_plan=_latest_peer_review_by_plan(
                self._peer_review_result_repository.list_by_run(run_id),
            ),
            self_correction_by_plan=_latest_exhausted_cycle_by_plan(
                self._self_correction_cycle_repository.list_by_run(run_id),
            ),
            existing_keys=existing_keys,
        )

    def list_approvals(self, user_id: str, run_id: str) -> list[HumanApprovalResponse]:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        approvals = self._approval_repository.list_by_run(run_id)
        return [
            HumanApprovalResponse.model_validate(approval.model_dump()) for approval in approvals
        ]

    def get_approval(self, user_id: str, run_id: str, approval_id: str) -> HumanApprovalResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        approval = self._approval_repository.get_by_id_for_run(approval_id, run_id)
        if approval is None:
            raise ApprovalNotFoundError(approval_id)

        return HumanApprovalResponse.model_validate(approval.model_dump())

    def get_approval_diff(
        self,
        user_id: str,
        run_id: str,
        approval_id: str,
    ) -> ApprovalDiffResponse:
        if self._run_repository.get_by_id_for_user(run_id, user_id) is None:
            raise RunNotFoundError(run_id)

        approval = self._approval_repository.get_by_id_for_run(approval_id, run_id)
        if approval is None:
            raise ApprovalNotFoundError(approval_id)
        if not approval.diff_artifact_path:
            raise ApprovalDiffNotFoundError(approval_id)

        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        try:
            content = read_workspace_text_file(workspace.root, approval.diff_artifact_path)
        except (WorkspaceArtifactNotFoundError, WorkspaceArtifactAccessError) as exc:
            raise ApprovalDiffNotFoundError(approval_id) from exc

        return ApprovalDiffResponse(
            approval_id=approval.approval_id,
            run_id=run_id,
            diff_path=approval.diff_artifact_path,
            content=content,
        )

    def submit_decision(
        self,
        user_id: str,
        run_id: str,
        approval_id: str,
        request: SubmitApprovalDecisionRequest,
    ) -> SubmitApprovalDecisionResponse:
        run = self._run_repository.get_by_id_for_user(run_id, user_id)
        if run is None:
            raise RunNotFoundError(run_id)

        approval = self._approval_repository.get_by_id_for_run(approval_id, run_id)
        if approval is None:
            raise ApprovalNotFoundError(approval_id)
        if approval.status != ApprovalStatus.PENDING:
            raise ApprovalAlreadyDecidedError(approval_id)

        if (
            request.decision == HumanDecision.REQUEST_CHANGES
            and not (request.feedback or "").strip()
        ):
            raise FeedbackRequiredError()

        decided_at = datetime.now(UTC)
        updated_approval = approval.model_copy(
            update={
                "human_decision": request.decision,
                "human_feedback": request.feedback,
                "decided_by_user_id": user_id,
                "decided_at": decided_at,
                "status": _map_decision_to_status(request.decision),
            },
        )
        workspace = self._run_service.get_workspace_for_run(user_id, run_id)
        output_dir = workspace.baseline / "approvals" / approval_id
        self._persist_approval(updated_approval, output_dir)

        replanning_required = False
        if request.decision == HumanDecision.REQUEST_CHANGES:
            self._append_human_feedback(workspace.baseline, updated_approval)
            replanning_required = True

        pending = self._approval_repository.list_pending_by_run(run_id)
        next_status = self._resolve_run_status_after_decision(
            request.decision,
            updated_approval.trigger,
            pending,
            replanning_required,
        )
        self._run_repository.update_status(run_id, user_id, next_status)
        self._write_approvals_artifact(workspace.baseline, run_id)
        self._emit_decision_event(run_id, updated_approval)

        logger.info(
            "Human approval decision recorded",
            extra={
                "run_id": run_id,
                "user_id": user_id,
                "approval_id": approval_id,
                "decision": request.decision.value,
                "stage": "human_approval",
            },
        )
        return SubmitApprovalDecisionResponse(
            approval=HumanApprovalResponse.model_validate(updated_approval.model_dump()),
            run_status=next_status.value,
            replanning_required=replanning_required,
        )

    def _persist_approval(self, approval: HumanApproval, output_dir: Path) -> HumanApproval:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "approval.json"
        approval = approval.model_copy(update={"artifact_path": str(artifact_path)})
        artifact_path.write_text(
            json.dumps(approval.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        existing = self._approval_repository.get_by_id_for_run(
            approval.approval_id,
            approval.run_id,
        )
        if existing is None:
            return self._approval_repository.add(approval)
        return self._approval_repository.update(approval)

    def _append_human_feedback(self, baseline_dir: Path, approval: HumanApproval) -> None:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / HUMAN_FEEDBACK_ARTIFACT_NAME
        entries: list[dict] = []
        if artifact_path.is_file():
            entries = json.loads(artifact_path.read_text(encoding="utf-8"))

        patch_plan = None
        if approval.patch_plan_id is not None:
            patch_plan = self._fix_plan_repository.get_by_id_for_run(
                approval.patch_plan_id,
                approval.run_id,
            )

        entries.append(
            {
                "approval_id": approval.approval_id,
                "patch_plan_id": approval.patch_plan_id,
                "issue_group_id": patch_plan.issue_group_id if patch_plan else None,
                "trigger": approval.trigger.value,
                "feedback": approval.human_feedback,
                "created_at": approval.decided_at.isoformat() if approval.decided_at else None,
            },
        )
        artifact_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def _emit_approval_required(self, run_id: str, approval: HumanApproval) -> None:
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=AgentEventType.APPROVAL_REQUIRED,
                stage=OrchestrationStage.HUMAN_APPROVAL,
                agent="human_approval_agent",
                payload={
                    "approval_id": approval.approval_id,
                    "patch_plan_id": approval.patch_plan_id,
                    "trigger": approval.trigger.value,
                    "reason": approval.reason,
                },
            ),
        )

    def _emit_decision_event(self, run_id: str, approval: HumanApproval) -> None:
        event_type = {
            HumanDecision.APPROVE: AgentEventType.HUMAN_APPROVED,
            HumanDecision.REJECT: AgentEventType.HUMAN_REJECTED,
            HumanDecision.REQUEST_CHANGES: AgentEventType.HUMAN_CHANGES_REQUESTED,
        }[approval.human_decision]
        emitter = AgentEventEmitter(run_id, self._event_repository)
        emitter.yield_event(
            WorkflowEvent(
                event_type=event_type,
                stage=OrchestrationStage.HUMAN_APPROVAL,
                agent="human_approval_agent",
                payload={
                    "approval_id": approval.approval_id,
                    "patch_plan_id": approval.patch_plan_id,
                    "decision": approval.human_decision.value if approval.human_decision else None,
                    "feedback": approval.human_feedback,
                },
            ),
        )

    @staticmethod
    def _resolve_run_status_after_decision(
        decision: HumanDecision,
        trigger: ApprovalTrigger,
        pending_approvals: list[HumanApproval],
        replanning_required: bool,
    ) -> RunStatus:
        if decision == HumanDecision.REJECT:
            return RunStatus.FAILED
        if decision == HumanDecision.REQUEST_CHANGES or replanning_required:
            return RunStatus.PLANNING
        if pending_approvals:
            return RunStatus.AWAITING_APPROVAL
        if trigger == ApprovalTrigger.RISK_GATE:
            return RunStatus.FIXING
        if trigger == ApprovalTrigger.PEER_REVIEW:
            return RunStatus.FINAL_REVIEW
        if trigger == ApprovalTrigger.SELF_CORRECTION_EXHAUSTED:
            return RunStatus.FIXING
        return RunStatus.AWAITING_APPROVAL

    def _write_approvals_artifact(self, baseline_dir: Path, run_id: str) -> Path:
        baseline_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = baseline_dir / APPROVALS_ARTIFACT_NAME
        approvals = self._approval_repository.list_by_run(run_id)
        payload = [approval.model_dump(mode="json") for approval in approvals]
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return artifact_path


def _map_decision_to_status(decision: HumanDecision) -> ApprovalStatus:
    return {
        HumanDecision.APPROVE: ApprovalStatus.APPROVED,
        HumanDecision.REJECT: ApprovalStatus.REJECTED,
        HumanDecision.REQUEST_CHANGES: ApprovalStatus.CHANGES_REQUESTED,
    }[decision]


def _latest_risk_by_plan(risk_decisions):
    latest: dict[str, object] = {}
    for decision in risk_decisions:
        existing = latest.get(decision.patch_plan_id)
        if existing is None or decision.created_at > existing.created_at:
            latest[decision.patch_plan_id] = decision
    return latest


def _latest_fix_attempts_by_plan(fix_attempts: list[FixAttempt]) -> dict[str, FixAttempt]:
    latest: dict[str, FixAttempt] = {}
    for attempt in fix_attempts:
        existing = latest.get(attempt.patch_plan_id)
        if existing is None or attempt.created_at > existing.created_at:
            latest[attempt.patch_plan_id] = attempt
    return latest


def _latest_peer_review_by_plan(
    peer_reviews: list[PeerReviewResult],
) -> dict[str, PeerReviewResult]:
    latest: dict[str, PeerReviewResult] = {}
    for review in peer_reviews:
        existing = latest.get(review.patch_plan_id)
        if existing is None or review.created_at > existing.created_at:
            latest[review.patch_plan_id] = review
    return latest


def _latest_exhausted_cycle_by_plan(
    cycles: list[SelfCorrectionCycle],
) -> dict[str, SelfCorrectionCycle]:
    latest: dict[str, SelfCorrectionCycle] = {}
    for cycle in cycles:
        existing = latest.get(cycle.patch_plan_id)
        if existing is None or cycle.created_at > existing.created_at:
            latest[cycle.patch_plan_id] = cycle
    return latest


def load_human_feedback_entries(baseline_dir: Path) -> list[dict]:
    artifact_path = baseline_dir / HUMAN_FEEDBACK_ARTIFACT_NAME
    if not artifact_path.is_file():
        return []
    return json.loads(artifact_path.read_text(encoding="utf-8"))
