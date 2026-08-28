from app.adk.risk.policy_engine import RiskPolicyEngine
from app.models.patch_plan import PatchPlan
from app.models.risk_decision import RiskDecision


class RiskAgent:
    """ADK specialist agent that assesses patch-plan risk via deterministic policy."""

    def __init__(self, policy_engine: RiskPolicyEngine | None = None) -> None:
        self._policy_engine = policy_engine or RiskPolicyEngine()

    def run(self, run_id: str, patch_plans: list[PatchPlan]) -> list[RiskDecision]:
        return self._policy_engine.assess(run_id, patch_plans)
