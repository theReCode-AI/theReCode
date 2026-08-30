from pathlib import Path

from app.adk.verification.engine import VerificationEngine, VerificationRunResult
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan


class VerificationAgent:
    """ADK specialist agent that validates applied fixes."""

    def __init__(self, engine: VerificationEngine | None = None) -> None:
        self._engine = engine

    def run(
        self,
        working_root: Path,
        patch_plan: PatchPlan,
        fix_attempt: FixAttempt,
        engine: VerificationEngine,
    ) -> VerificationRunResult:
        verifier = self._engine or engine
        return verifier.verify(working_root, patch_plan, fix_attempt)
