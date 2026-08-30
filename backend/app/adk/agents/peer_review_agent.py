from pathlib import Path

from app.adk.peer_review.engine import PeerReviewEngine, PeerReviewExecutionResult
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.project_intelligence import ProjectIntelligence
from app.models.regression_test_result import RegressionTestResult
from app.models.verification_result import VerificationResult


class PeerReviewAgent:
    """ADK specialist agent that coordinates multi-agent peer review."""

    def __init__(self, engine: PeerReviewEngine | None = None) -> None:
        self._engine = engine

    def run(
        self,
        working_root: Path,
        patch_plan: PatchPlan,
        fix_attempt: FixAttempt,
        verification_result: VerificationResult,
        regression_test_result: RegressionTestResult,
        project_intelligence: ProjectIntelligence | None,
        engine: PeerReviewEngine,
    ) -> PeerReviewExecutionResult:
        runner = self._engine or engine
        return runner.review(
            working_root,
            patch_plan,
            fix_attempt,
            verification_result,
            regression_test_result,
            project_intelligence,
        )
