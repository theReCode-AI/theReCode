"""Extract durable project memories from run artifacts and persisted results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from bson import ObjectId

from app.models.approval import HumanApproval
from app.models.approval_enums import ApprovalStatus
from app.models.fix_attempt import FixAttempt
from app.models.fix_attempt_enums import FixAttemptStatus
from app.models.memory_entry import MemoryEntry
from app.models.memory_enums import MemoryType
from app.models.patch_plan import PatchPlan
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.peer_review_result import PeerReviewResult
from app.models.project_intelligence import ProjectIntelligence
from app.models.regression_test_enums import RegressionTestStatus
from app.models.regression_test_result import RegressionTestResult
from app.models.run import Run
from app.models.self_correction_cycle import SelfCorrectionCycle
from app.models.self_correction_enums import SelfCorrectionStatus
from app.models.verification_enums import VerificationStatus
from app.models.verification_result import VerificationResult


@dataclass(frozen=True)
class MemoryExtractionContext:
    run: Run
    patch_plans: list[PatchPlan]
    approvals: list[HumanApproval]
    fix_attempts: list[FixAttempt]
    verification_results: list[VerificationResult]
    regression_results: list[RegressionTestResult]
    peer_reviews: list[PeerReviewResult]
    self_correction_cycles: list[SelfCorrectionCycle]


class MemoryExtractor:
    """Build memory entries from a completed or in-progress run."""

    def extract(self, context: MemoryExtractionContext) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        entries.extend(self._extract_project_memory(context))
        entries.extend(self._extract_decision_memory(context))
        entries.extend(self._extract_failure_memory(context))
        entries.extend(self._extract_success_memory(context))
        return entries

    def _extract_project_memory(self, context: MemoryExtractionContext) -> list[MemoryEntry]:
        intelligence = context.run.project_intelligence
        if intelligence is None:
            return []

        return [
            self._entry(
                context,
                MemoryType.PROJECT,
                "project_intelligence",
                "Project intelligence snapshot",
                _format_project_intelligence(intelligence),
                tags=["architecture", "project"],
                metadata=intelligence.model_dump(mode="json"),
            ),
        ]

    def _extract_decision_memory(self, context: MemoryExtractionContext) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for approval in context.approvals:
            if approval.status == ApprovalStatus.PENDING:
                continue
            entries.append(
                self._entry(
                    context,
                    MemoryType.DECISION,
                    f"approval:{approval.approval_id}",
                    _decision_title(approval),
                    _format_approval_memory(approval),
                    tags=["human", approval.trigger.value],
                    metadata={
                        "approval_id": approval.approval_id,
                        "patch_plan_id": approval.patch_plan_id,
                        "decision": (
                            approval.human_decision.value if approval.human_decision else None
                        ),
                        "feedback": approval.human_feedback,
                    },
                ),
            )
        return entries

    def _extract_failure_memory(self, context: MemoryExtractionContext) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for result in context.verification_results:
            if result.status != VerificationStatus.FAILED:
                continue
            entries.append(
                self._entry(
                    context,
                    MemoryType.FAILURE,
                    f"verification:{result.verification_result_id}",
                    "Verification failed",
                    result.failure_summary or "Verification checks failed",
                    tags=["verification", "failure", result.patch_plan_id],
                    metadata={"patch_plan_id": result.patch_plan_id},
                ),
            )

        for cycle in context.self_correction_cycles:
            if cycle.status not in {SelfCorrectionStatus.FAILED, SelfCorrectionStatus.EXHAUSTED}:
                continue
            entries.append(
                self._entry(
                    context,
                    MemoryType.FAILURE,
                    f"self_correction:{cycle.self_correction_cycle_id}",
                    "Self-correction did not recover",
                    cycle.failure_summary,
                    tags=["self_correction", "failure", cycle.patch_plan_id],
                    metadata={"patch_plan_id": cycle.patch_plan_id, "status": cycle.status.value},
                ),
            )

        for result in context.regression_results:
            if result.status not in {RegressionTestStatus.FAILED, RegressionTestStatus.ERROR}:
                continue
            entries.append(
                self._entry(
                    context,
                    MemoryType.FAILURE,
                    f"regression:{result.regression_test_id}",
                    "Regression testing failed",
                    result.failure_summary or "Regression suite failed",
                    tags=["regression", "failure", result.patch_plan_id],
                    metadata={"patch_plan_id": result.patch_plan_id},
                ),
            )

        for review in context.peer_reviews:
            if review.verdict != PeerReviewVerdict.REJECTED:
                continue
            entries.append(
                self._entry(
                    context,
                    MemoryType.FAILURE,
                    f"peer_review:{review.peer_review_id}",
                    "Peer review rejected the fix",
                    review.synthesis_summary,
                    tags=["peer_review", "failure", review.patch_plan_id],
                    metadata={"patch_plan_id": review.patch_plan_id},
                ),
            )

        return entries

    def _extract_success_memory(self, context: MemoryExtractionContext) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        plans_by_id = {plan.patch_plan_id: plan for plan in context.patch_plans}

        for attempt in context.fix_attempts:
            if attempt.status != FixAttemptStatus.APPLIED:
                continue
            patch_plan = plans_by_id.get(attempt.patch_plan_id)
            if patch_plan is None:
                continue

            passed_verification = any(
                result.patch_plan_id == attempt.patch_plan_id
                and result.status == VerificationStatus.PASSED
                for result in context.verification_results
            )
            approved_review = any(
                review.patch_plan_id == attempt.patch_plan_id
                and review.verdict == PeerReviewVerdict.APPROVED
                for review in context.peer_reviews
            )
            if not passed_verification and not approved_review:
                continue

            entries.append(
                self._entry(
                    context,
                    MemoryType.SUCCESS_STRATEGY,
                    f"fix_attempt:{attempt.fix_attempt_id}",
                    f"Successful remediation: {patch_plan.title}",
                    patch_plan.solution_rationale,
                    tags=_success_tags(patch_plan),
                    metadata={
                        "patch_plan_id": patch_plan.patch_plan_id,
                        "changed_files": attempt.changed_files,
                        "root_cause": patch_plan.root_cause,
                    },
                ),
            )

        for result in context.regression_results:
            if not result.eligible or result.status != RegressionTestStatus.PASSED:
                continue
            entries.append(
                self._entry(
                    context,
                    MemoryType.SUCCESS_STRATEGY,
                    f"regression_success:{result.regression_test_id}",
                    "Regression test strategy succeeded",
                    f"Generated regression test at {result.test_file_path}",
                    tags=["regression", "testing", result.patch_plan_id],
                    metadata={
                        "patch_plan_id": result.patch_plan_id,
                        "test_file_path": result.test_file_path,
                    },
                ),
            )

        return entries

    def _entry(
        self,
        context: MemoryExtractionContext,
        memory_type: MemoryType,
        source_key: str,
        title: str,
        content: str,
        tags: list[str],
        metadata: dict,
    ) -> MemoryEntry:
        return MemoryEntry(
            memory_id=str(ObjectId()),
            project_id=context.run.project_id,
            run_id=context.run.id,
            memory_type=memory_type,
            title=title,
            content=content,
            tags=tags,
            metadata=metadata,
            source_key=source_key,
            created_at=datetime.now(UTC),
        )


def _format_project_intelligence(intelligence: ProjectIntelligence) -> str:
    return (
        f"Architecture={intelligence.architecture.value}; "
        f"package_manager={intelligence.package_manager.value}; "
        f"frameworks={', '.join(intelligence.frameworks) or 'none'}; "
        f"entrypoints={', '.join(intelligence.entrypoints) or 'none'}; "
        f"source_directories={', '.join(intelligence.source_directories) or 'none'}; "
        f"test_directories={', '.join(intelligence.test_directories) or 'none'}"
    )


def _format_approval_memory(approval: HumanApproval) -> str:
    parts = [approval.reason]
    if approval.human_feedback:
        parts.append(f"Feedback: {approval.human_feedback}")
    return " ".join(parts)


def _decision_title(approval: HumanApproval) -> str:
    decision = approval.human_decision.value if approval.human_decision else approval.status.value
    return f"Human decision: {decision}"


def _success_tags(patch_plan: PatchPlan) -> list[str]:
    tags = ["success", patch_plan.patch_plan_id]
    tags.extend(modification.change_type for modification in patch_plan.expected_modifications)
    return tags
