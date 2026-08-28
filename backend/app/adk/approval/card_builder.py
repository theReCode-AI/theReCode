"""Build human approval cards from run artifacts and persisted results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from bson import ObjectId

from app.models.approval import HumanApproval
from app.models.approval_enums import ApprovalStatus, ApprovalTrigger
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.peer_review_result import PeerReviewResult
from app.models.risk_decision import RiskDecision
from app.models.self_correction_cycle import SelfCorrectionCycle
from app.models.self_correction_enums import SelfCorrectionStatus
from app.models.verification_result import VerificationResult


@dataclass(frozen=True)
class ApprovalBuildContext:
    patch_plans_by_id: dict[str, PatchPlan]
    risk_decisions_by_plan: dict[str, RiskDecision]
    fix_attempts_by_plan: dict[str, FixAttempt]
    verifications_by_plan: dict[str, VerificationResult]
    peer_reviews_by_plan: dict[str, PeerReviewResult]
    self_correction_by_plan: dict[str, SelfCorrectionCycle]
    existing_keys: set[tuple[str, str | None]]


def build_pending_approvals(
    run_id: str,
    context: ApprovalBuildContext,
) -> list[HumanApproval]:
    approvals: list[HumanApproval] = []
    now = datetime.now(UTC)

    for patch_plan_id, risk_decision in context.risk_decisions_by_plan.items():
        if not risk_decision.approval_required:
            continue
        key = (ApprovalTrigger.RISK_GATE.value, patch_plan_id)
        if key in context.existing_keys:
            continue
        patch_plan = context.patch_plans_by_id.get(patch_plan_id)
        if patch_plan is None:
            continue
        approvals.append(
            _build_risk_gate_approval(run_id, patch_plan, risk_decision, now),
        )

    for patch_plan_id, peer_review in context.peer_reviews_by_plan.items():
        if peer_review.verdict not in {
            PeerReviewVerdict.CHANGES_REQUESTED,
            PeerReviewVerdict.REJECTED,
        }:
            continue
        key = (ApprovalTrigger.PEER_REVIEW.value, patch_plan_id)
        if key in context.existing_keys:
            continue
        patch_plan = context.patch_plans_by_id.get(patch_plan_id)
        if patch_plan is None:
            continue
        fix_attempt = context.fix_attempts_by_plan.get(patch_plan_id)
        verification = context.verifications_by_plan.get(peer_review.verification_result_id)
        approvals.append(
            _build_peer_review_approval(
                run_id,
                patch_plan,
                peer_review,
                fix_attempt,
                verification,
                now,
            ),
        )

    for patch_plan_id, cycle in context.self_correction_by_plan.items():
        if cycle.status != SelfCorrectionStatus.EXHAUSTED:
            continue
        key = (ApprovalTrigger.SELF_CORRECTION_EXHAUSTED.value, patch_plan_id)
        if key in context.existing_keys:
            continue
        patch_plan = context.patch_plans_by_id.get(patch_plan_id)
        if patch_plan is None:
            continue
        approvals.append(
            _build_self_correction_approval(run_id, patch_plan, cycle, now),
        )

    return approvals


def _build_risk_gate_approval(
    run_id: str,
    patch_plan: PatchPlan,
    risk_decision: RiskDecision,
    created_at: datetime,
) -> HumanApproval:
    return HumanApproval(
        approval_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan.patch_plan_id,
        trigger=ApprovalTrigger.RISK_GATE,
        status=ApprovalStatus.PENDING,
        reason=risk_decision.rationale,
        issue_title=patch_plan.title,
        root_cause=patch_plan.root_cause,
        risk_level=risk_decision.assessed_risk,
        affected_files=list(patch_plan.affected_files),
        evidence_summary=_join_rules(risk_decision.policy_rules),
        expected_tests=list(patch_plan.expected_tests),
        confidence=risk_decision.assessed_risk.value,
        created_at=created_at,
    )


def _build_peer_review_approval(
    run_id: str,
    patch_plan: PatchPlan,
    peer_review: PeerReviewResult,
    fix_attempt: FixAttempt | None,
    verification: VerificationResult | None,
    created_at: datetime,
) -> HumanApproval:
    reason = peer_review.synthesis_summary
    if peer_review.verdict == PeerReviewVerdict.REJECTED:
        reason = f"Peer review rejected the fix: {peer_review.synthesis_summary}"

    return HumanApproval(
        approval_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan.patch_plan_id,
        trigger=ApprovalTrigger.PEER_REVIEW,
        status=ApprovalStatus.PENDING,
        reason=reason,
        issue_title=patch_plan.title,
        root_cause=patch_plan.root_cause,
        risk_level=patch_plan.estimated_risk,
        affected_files=list(patch_plan.affected_files),
        diff_artifact_path=fix_attempt.diff_artifact_path if fix_attempt else None,
        evidence_summary=peer_review.synthesis_summary,
        expected_tests=list(patch_plan.expected_tests),
        verification_summary=_verification_summary(verification),
        reviewer_feedback=list(peer_review.blocking_issues),
        confidence=peer_review.verdict.value,
        created_at=created_at,
    )


def _build_self_correction_approval(
    run_id: str,
    patch_plan: PatchPlan,
    cycle: SelfCorrectionCycle,
    created_at: datetime,
) -> HumanApproval:
    return HumanApproval(
        approval_id=str(ObjectId()),
        run_id=run_id,
        patch_plan_id=patch_plan.patch_plan_id,
        trigger=ApprovalTrigger.SELF_CORRECTION_EXHAUSTED,
        status=ApprovalStatus.PENDING,
        reason="Maximum self-correction iterations were exhausted",
        issue_title=patch_plan.title,
        root_cause=cycle.root_cause,
        risk_level=patch_plan.estimated_risk,
        affected_files=list(patch_plan.affected_files),
        evidence_summary=cycle.failure_summary,
        expected_tests=list(patch_plan.expected_tests),
        reviewer_feedback=[cycle.failure_summary],
        confidence="exhausted",
        created_at=created_at,
    )


def _latest_fix_attempt_for_plan(
    fix_attempts_by_plan: dict[str, FixAttempt],
    patch_plan_id: str,
) -> FixAttempt | None:
    return fix_attempts_by_plan.get(patch_plan_id)


def _verification_summary(verification: VerificationResult | None) -> str | None:
    if verification is None:
        return None
    return (
        f"status={verification.status.value}; "
        f"passed={verification.passed_checks}; "
        f"failed={verification.failed_checks}"
    )


def _join_rules(policy_rules: list[str]) -> str | None:
    if not policy_rules:
        return None
    return ", ".join(policy_rules)
