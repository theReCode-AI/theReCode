from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.self_correction_cycle import SelfCorrectionCycle


class SelfCorrectionCycleNotFoundError(Exception):
    def __init__(self, self_correction_cycle_id: str) -> None:
        self.self_correction_cycle_id = self_correction_cycle_id
        super().__init__(f"Self-correction cycle not found: {self_correction_cycle_id}")


class SelfCorrectionCycleRepository(BaseRepository):
    """Repository for persisted self-correction cycles."""

    collection_name = collections.SELF_CORRECTION_CYCLES

    def add(self, cycle: SelfCorrectionCycle) -> SelfCorrectionCycle:
        document = cycle.model_dump(mode="json")
        document["_id"] = ObjectId(cycle.self_correction_cycle_id)
        document["run_id"] = ObjectId(cycle.run_id)
        document["patch_plan_id"] = ObjectId(cycle.patch_plan_id)
        document["prior_fix_attempt_id"] = ObjectId(cycle.prior_fix_attempt_id)
        document["prior_verification_result_id"] = ObjectId(cycle.prior_verification_result_id)
        if cycle.retry_fix_attempt_id is not None:
            document["retry_fix_attempt_id"] = ObjectId(cycle.retry_fix_attempt_id)
        if cycle.retry_verification_result_id is not None:
            document["retry_verification_result_id"] = ObjectId(
                cycle.retry_verification_result_id,
            )
        self.collection.insert_one(document)
        return cycle

    def list_by_run(self, run_id: str) -> list[SelfCorrectionCycle]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [SelfCorrectionCycle.from_document(document) for document in documents]

    def get_by_id_for_run(
        self,
        self_correction_cycle_id: str,
        run_id: str,
    ) -> SelfCorrectionCycle | None:
        document = self.collection.find_one(
            {
                "_id": ObjectId(self_correction_cycle_id),
                "run_id": ObjectId(run_id),
            },
        )
        if document is None:
            return None
        return SelfCorrectionCycle.from_document(document)
