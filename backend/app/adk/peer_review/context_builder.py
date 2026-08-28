"""Assemble peer review inputs from workspace artifacts and persisted results."""

from __future__ import annotations

from pathlib import Path

from app.adk.peer_review.context import PeerReviewContext
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.project_intelligence import ProjectIntelligence
from app.models.regression_test_result import RegressionTestResult
from app.models.verification_result import VerificationResult


def build_peer_review_context(
    working_root: Path,
    patch_plan: PatchPlan,
    fix_attempt: FixAttempt,
    verification_result: VerificationResult,
    regression_test_result: RegressionTestResult,
    project_intelligence: ProjectIntelligence | None,
) -> PeerReviewContext:
    diff_text = _read_diff_text(fix_attempt)
    return PeerReviewContext(
        patch_plan=patch_plan,
        fix_attempt=fix_attempt,
        verification_result=verification_result,
        regression_test_result=regression_test_result,
        diff_text=diff_text,
        project_intelligence=project_intelligence,
        working_root=working_root,
    )


def _read_diff_text(fix_attempt: FixAttempt) -> str:
    if not fix_attempt.diff_artifact_path:
        return ""
    diff_path = Path(fix_attempt.diff_artifact_path)
    if not diff_path.is_file():
        return ""
    return diff_path.read_text(encoding="utf-8")
