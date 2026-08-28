"""Run independent peer reviewers and synthesize a final verdict."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.adk.peer_review.context_builder import build_peer_review_context
from app.adk.peer_review.reviewers import (
    ArchitectureReviewer,
    PeerReviewSynthesizer,
    SecurityReviewer,
    TestingReviewer,
)
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.peer_review_enums import PeerReviewVerdict
from app.models.peer_review_result import ReviewerOpinion
from app.models.project_intelligence import ProjectIntelligence
from app.models.regression_test_result import RegressionTestResult
from app.models.verification_result import VerificationResult


@dataclass(frozen=True)
class PeerReviewExecutionResult:
    verdict: PeerReviewVerdict
    reviewer_opinions: list[ReviewerOpinion]
    synthesis_summary: str
    blocking_issues: list[str]
    diff_artifact_path: str | None


class PeerReviewEngine:
    """Coordinate specialist reviewers and synthesize the final decision."""

    def __init__(
        self,
        security_reviewer: SecurityReviewer | None = None,
        testing_reviewer: TestingReviewer | None = None,
        architecture_reviewer: ArchitectureReviewer | None = None,
        synthesizer: PeerReviewSynthesizer | None = None,
    ) -> None:
        self._security_reviewer = security_reviewer or SecurityReviewer()
        self._testing_reviewer = testing_reviewer or TestingReviewer()
        self._architecture_reviewer = architecture_reviewer or ArchitectureReviewer()
        self._synthesizer = synthesizer or PeerReviewSynthesizer()

    def review(
        self,
        working_root: Path,
        patch_plan: PatchPlan,
        fix_attempt: FixAttempt,
        verification_result: VerificationResult,
        regression_test_result: RegressionTestResult,
        project_intelligence: ProjectIntelligence | None,
    ) -> PeerReviewExecutionResult:
        context = build_peer_review_context(
            working_root,
            patch_plan,
            fix_attempt,
            verification_result,
            regression_test_result,
            project_intelligence,
        )
        specialist_opinions = [
            self._security_reviewer.review(context),
            self._testing_reviewer.review(context),
            self._architecture_reviewer.review(context),
        ]
        verdict, synthesis_summary, blocking_issues = self._synthesizer.synthesize(
            specialist_opinions,
        )
        return PeerReviewExecutionResult(
            verdict=verdict,
            reviewer_opinions=specialist_opinions,
            synthesis_summary=synthesis_summary,
            blocking_issues=blocking_issues,
            diff_artifact_path=fix_attempt.diff_artifact_path,
        )
