"""Inputs assembled for independent peer reviewers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.project_intelligence import ProjectIntelligence
from app.models.regression_test_result import RegressionTestResult
from app.models.verification_result import VerificationResult


@dataclass(frozen=True)
class PeerReviewContext:
    """Read-only review context for a single patch plan."""

    patch_plan: PatchPlan
    fix_attempt: FixAttempt
    verification_result: VerificationResult
    regression_test_result: RegressionTestResult
    diff_text: str
    project_intelligence: ProjectIntelligence | None
    working_root: Path
