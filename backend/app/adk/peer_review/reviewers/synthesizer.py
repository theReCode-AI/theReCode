"""Aggregate independent reviewer opinions into a final verdict."""

from __future__ import annotations

from app.models.peer_review_enums import PeerReviewVerdict, ReviewerDecision, ReviewerRole
from app.models.peer_review_result import ReviewerOpinion


class PeerReviewSynthesizer:
    """Combine specialist reviewer decisions without modifying code."""

    role = ReviewerRole.SYNTHESIZER

    def synthesize(
        self,
        opinions: list[ReviewerOpinion],
    ) -> tuple[PeerReviewVerdict, str, list[str]]:
        specialist_opinions = [
            opinion for opinion in opinions if opinion.reviewer != self.role
        ]
        blocking_issues = _collect_blocking_issues(specialist_opinions)
        verdict = _resolve_verdict(specialist_opinions)
        summary = _build_summary(verdict, specialist_opinions)
        return verdict, summary, blocking_issues


def _collect_blocking_issues(opinions: list[ReviewerOpinion]) -> list[str]:
    issues: list[str] = []
    for opinion in opinions:
        if opinion.decision == ReviewerDecision.APPROVE:
            continue
        prefix = opinion.reviewer.value.replace("_", " ")
        for finding in opinion.findings:
            issues.append(f"{prefix}: {finding}")
        if not opinion.findings:
            issues.append(f"{prefix}: {opinion.summary}")
    return issues


def _resolve_verdict(opinions: list[ReviewerOpinion]) -> PeerReviewVerdict:
    if any(opinion.decision == ReviewerDecision.REJECT for opinion in opinions):
        return PeerReviewVerdict.REJECTED
    if any(opinion.decision == ReviewerDecision.REQUEST_CHANGES for opinion in opinions):
        return PeerReviewVerdict.CHANGES_REQUESTED
    return PeerReviewVerdict.APPROVED


def _build_summary(verdict: PeerReviewVerdict, opinions: list[ReviewerOpinion]) -> str:
    approve_count = sum(
        1 for opinion in opinions if opinion.decision == ReviewerDecision.APPROVE
    )
    if verdict == PeerReviewVerdict.APPROVED:
        return f"All {approve_count} specialist reviewers approved the change"
    if verdict == PeerReviewVerdict.REJECTED:
        return "Peer review rejected the change due to blocking reviewer findings"
    return "Peer review requested changes before the fix can proceed"
