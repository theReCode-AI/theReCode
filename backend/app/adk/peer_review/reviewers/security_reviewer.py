"""Security-focused peer reviewer."""

from __future__ import annotations

import re

from app.adk.peer_review.context import PeerReviewContext
from app.models.patch_plan_enums import RiskLevel
from app.models.peer_review_enums import ReviewerDecision, ReviewerRole
from app.models.peer_review_result import ReviewerOpinion

DANGEROUS_DIFF_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\beval\s*\("), "Introduces or retains eval() usage"),
    (re.compile(r"\bexec\s*\("), "Introduces or retains exec() usage"),
    (re.compile(r"os\.system\s*\("), "Uses os.system for command execution"),
    (
        re.compile(r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True"),
        "Uses subprocess with shell=True",
    ),
    (re.compile(r"pickle\.loads\s*\("), "Uses pickle.loads which is unsafe on untrusted data"),
    (re.compile(r"yaml\.load\s*\("), "Uses yaml.load without SafeLoader"),
    (
        re.compile(r"(?i)(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]+['\"]"),
        "Hardcoded credential pattern",
    ),
)


class SecurityReviewer:
    """Inspect diffs and fix metadata for security regressions."""

    role = ReviewerRole.SECURITY

    def review(self, context: PeerReviewContext) -> ReviewerOpinion:
        findings: list[str] = []

        if context.fix_attempt.scope_violation:
            findings.append("Fix attempt modified files outside the approved scope")

        if context.fix_attempt.unexpected_files:
            findings.append(
                "Unexpected files changed: " + ", ".join(context.fix_attempt.unexpected_files),
            )

        added_lines = _extract_added_diff_lines(context.diff_text)
        added_diff_text = "\n".join(added_lines)
        for pattern, message in DANGEROUS_DIFF_PATTERNS:
            if pattern.search(added_diff_text):
                findings.append(message)

        if context.patch_plan.estimated_risk in {RiskLevel.CRITICAL, RiskLevel.BLOCKED}:
            findings.append(
                f"Patch plan risk level is {context.patch_plan.estimated_risk.value}",
            )

        decision = _resolve_decision(findings, context.patch_plan.estimated_risk)
        summary = _build_summary(decision, findings)
        return ReviewerOpinion(
            reviewer=self.role,
            decision=decision,
            summary=summary,
            findings=findings,
        )


def _resolve_decision(findings: list[str], risk_level: RiskLevel) -> ReviewerDecision:
    if not findings:
        return ReviewerDecision.APPROVE
    if risk_level in {RiskLevel.CRITICAL, RiskLevel.BLOCKED}:
        return ReviewerDecision.REJECT
    if any("scope" in finding.lower() or "unexpected" in finding.lower() for finding in findings):
        return ReviewerDecision.REJECT
    if any("eval" in finding.lower() or "exec" in finding.lower() for finding in findings):
        return ReviewerDecision.REJECT
    return ReviewerDecision.REQUEST_CHANGES


def _extract_added_diff_lines(diff_text: str) -> list[str]:
    added_lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added_lines.append(line[1:])
    return added_lines


def _build_summary(decision: ReviewerDecision, findings: list[str]) -> str:
    if decision == ReviewerDecision.APPROVE:
        return "No security concerns identified in the reviewed diff"
    if decision == ReviewerDecision.REJECT:
        return "Security review blocked the change due to critical findings"
    return f"Security review requested changes ({len(findings)} finding(s))"
