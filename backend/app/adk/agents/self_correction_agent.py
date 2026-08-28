from app.adk.fixing.applicator import FixApplicator
from app.adk.self_correction.engine import SelfCorrectionEngine, SelfCorrectionRunResult
from app.adk.verification.engine import VerificationEngine
from app.models.fix_attempt import FixAttempt
from app.models.patch_plan import PatchPlan
from app.models.risk_decision import RiskDecision
from app.models.verification_result import VerificationResult
from app.workspace.models import RunWorkspace


class SelfCorrectionAgent:
    """ADK specialist agent that retries fixes after verification failure."""

    def __init__(self, engine: SelfCorrectionEngine | None = None) -> None:
        self._engine = engine or SelfCorrectionEngine()

    def run(
        self,
        workspace: RunWorkspace,
        patch_plan: PatchPlan,
        risk_decision: RiskDecision,
        prior_fix_attempt: FixAttempt,
        prior_verification: VerificationResult,
        applicator: FixApplicator,
        verification_engine: VerificationEngine,
    ) -> SelfCorrectionRunResult:
        return self._engine.correct(
            workspace,
            patch_plan,
            risk_decision,
            prior_fix_attempt,
            prior_verification,
            applicator,
            verification_engine,
        )
