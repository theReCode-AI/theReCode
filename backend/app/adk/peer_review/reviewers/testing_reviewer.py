"""Testing-focused peer reviewer."""

from __future__ import annotations

from app.adk.peer_review.context import PeerReviewContext
from app.adk.regression.generator import MEANINGLESS_CHANGE_TYPES
from app.models.peer_review_enums import ReviewerDecision, ReviewerRole
from app.models.peer_review_result import ReviewerOpinion
from app.models.regression_test_enums import RegressionTestStatus


class TestingReviewer:
    """Validate verification and regression evidence for the fix."""

    role = ReviewerRole.TESTING

    def review(self, context: PeerReviewContext) -> ReviewerOpinion:
        findings: list[str] = []
        regression = context.regression_test_result
        verification = context.verification_result

        if verification.failed_checks > 0:
            findings.append("Verification reported failed checks")

        if regression.status == RegressionTestStatus.FAILED:
            findings.append("Regression tests failed")
        elif regression.status == RegressionTestStatus.ERROR:
            findings.append("Regression test execution errored")

        change_types = {
            modification.change_type for modification in context.patch_plan.expected_modifications
        }
        meaningful_fix = not change_types or not change_types.issubset(MEANINGLESS_CHANGE_TYPES)

        if meaningful_fix and not context.patch_plan.expected_tests:
            findings.append("Meaningful fix lacks documented expected tests")

        if regression.eligible and regression.status == RegressionTestStatus.PASSED:
            if regression.targeted_passed < 1:
                findings.append("Targeted regression suite reported zero passing tests")

        if meaningful_fix and regression.eligible and not regression.test_file_path:
            findings.append("Eligible regression test file was not generated")

        decision = _resolve_decision(findings, regression.status)
        summary = _build_summary(decision, findings)
        return ReviewerOpinion(
            reviewer=self.role,
            decision=decision,
            summary=summary,
            findings=findings,
        )


def _resolve_decision(
    findings: list[str],
    regression_status: RegressionTestStatus,
) -> ReviewerDecision:
    if regression_status in {RegressionTestStatus.FAILED, RegressionTestStatus.ERROR}:
        return ReviewerDecision.REJECT
    if not findings:
        return ReviewerDecision.APPROVE
    if any("failed" in finding.lower() or "errored" in finding.lower() for finding in findings):
        return ReviewerDecision.REJECT
    return ReviewerDecision.REQUEST_CHANGES


def _build_summary(decision: ReviewerDecision, findings: list[str]) -> str:
    if decision == ReviewerDecision.APPROVE:
        return "Testing evidence supports the proposed fix"
    if decision == ReviewerDecision.REJECT:
        return "Testing review rejected the change due to failed verification evidence"
    return f"Testing review requested additional coverage ({len(findings)} finding(s))"
