from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.risk_decision import RiskDecision


class RiskDecisionNotFoundError(Exception):
    def __init__(self, risk_decision_id: str) -> None:
        self.risk_decision_id = risk_decision_id
        super().__init__(f"Risk decision not found: {risk_decision_id}")


class RiskDecisionRepository(BaseRepository):
    """Repository for persisted risk decisions."""

    collection_name = collections.RISK_DECISIONS

    def replace_for_run(
        self,
        run_id: str,
        risk_decisions: list[RiskDecision],
    ) -> list[RiskDecision]:
        self.collection.delete_many({"run_id": ObjectId(run_id)})
        if not risk_decisions:
            return []

        documents = []
        for risk_decision in risk_decisions:
            document = risk_decision.model_dump(mode="json")
            document["_id"] = ObjectId(risk_decision.risk_decision_id)
            document["run_id"] = ObjectId(run_id)
            document["patch_plan_id"] = ObjectId(risk_decision.patch_plan_id)
            documents.append(document)

        self.collection.insert_many(documents)
        return risk_decisions

    def list_by_run(self, run_id: str) -> list[RiskDecision]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [RiskDecision.from_document(document) for document in documents]

    def get_by_id_for_run(self, risk_decision_id: str, run_id: str) -> RiskDecision | None:
        document = self.collection.find_one(
            {"_id": ObjectId(risk_decision_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return RiskDecision.from_document(document)
