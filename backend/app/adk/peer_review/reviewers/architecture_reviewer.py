"""Architecture-focused peer reviewer."""

from __future__ import annotations

from app.adk.peer_review.context import PeerReviewContext
from app.models.patch_plan_enums import FixScope, RiskLevel
from app.models.peer_review_enums import ReviewerDecision, ReviewerRole
from app.models.peer_review_result import ReviewerOpinion


class ArchitectureReviewer:
    """Ensure the fix aligns with repository structure and planning rationale."""

    role = ReviewerRole.ARCHITECTURE

    def review(self, context: PeerReviewContext) -> ReviewerOpinion:
        findings: list[str] = []
        patch_plan = context.patch_plan
        intelligence = context.project_intelligence

        if not patch_plan.solution_rationale.strip():
            findings.append("Patch plan is missing solution rationale")

        if not patch_plan.rollback_strategy.strip():
            findings.append("Patch plan is missing rollback strategy")

        if patch_plan.expected_scope == FixScope.REPOSITORY:
            findings.append("Repository-wide scope requires architecture scrutiny")

        if patch_plan.estimated_risk in {RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.BLOCKED}:
            findings.append(
                f"Patch plan risk level is {patch_plan.estimated_risk.value}",
            )

        if intelligence is not None and intelligence.source_directories:
            for changed_file in context.fix_attempt.changed_files:
                if not _is_under_source_directories(changed_file, intelligence.source_directories):
                    findings.append(
                        f"Changed file '{changed_file}' is outside detected source directories",
                    )

        decision = _resolve_decision(findings)
        summary = _build_summary(decision, findings)
        return ReviewerOpinion(
            reviewer=self.role,
            decision=decision,
            summary=summary,
            findings=findings,
        )


def _is_under_source_directories(changed_file: str, source_directories: list[str]) -> bool:
    normalized = changed_file.replace("\\", "/")
    for source_directory in source_directories:
        prefix = source_directory.rstrip("/") + "/"
        if normalized == source_directory.rstrip("/") or normalized.startswith(prefix):
            return True
    return False


def _resolve_decision(findings: list[str]) -> ReviewerDecision:
    if not findings:
        return ReviewerDecision.APPROVE
    if any("repository-wide" in finding.lower() for finding in findings):
        return ReviewerDecision.REQUEST_CHANGES
    if any("outside detected source" in finding.lower() for finding in findings):
        return ReviewerDecision.REQUEST_CHANGES
    if any("missing" in finding.lower() for finding in findings):
        return ReviewerDecision.REQUEST_CHANGES
    return ReviewerDecision.REQUEST_CHANGES


def _build_summary(decision: ReviewerDecision, findings: list[str]) -> str:
    if decision == ReviewerDecision.APPROVE:
        return "Architecture review found no structural concerns"
    if decision == ReviewerDecision.REJECT:
        return "Architecture review rejected the change"
    return f"Architecture review requested plan improvements ({len(findings)} finding(s))"
