from app.db.repositories.risk_decision_repository import RiskDecisionRepository
from app.models.risk_decision import RiskDecision


class InMemoryRiskDecisionRepository(RiskDecisionRepository):
    def __init__(self) -> None:
        self._risk_decisions: dict[str, list[RiskDecision]] = {}

    def replace_for_run(
        self,
        run_id: str,
        risk_decisions: list[RiskDecision],
    ) -> list[RiskDecision]:
        self._risk_decisions[run_id] = list(risk_decisions)
        return list(risk_decisions)

    def list_by_run(self, run_id: str) -> list[RiskDecision]:
        return list(self._risk_decisions.get(run_id, []))

    def get_by_id_for_run(self, risk_decision_id: str, run_id: str) -> RiskDecision | None:
        for risk_decision in self._risk_decisions.get(run_id, []):
            if risk_decision.risk_decision_id == risk_decision_id:
                return risk_decision
        return None
