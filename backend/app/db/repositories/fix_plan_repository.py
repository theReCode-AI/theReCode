from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.patch_plan import PatchPlan


class FixPlanNotFoundError(Exception):
    def __init__(self, patch_plan_id: str) -> None:
        self.patch_plan_id = patch_plan_id
        super().__init__(f"Patch plan not found: {patch_plan_id}")


class FixPlanRepository(BaseRepository):
    """Repository for persisted patch plans."""

    collection_name = collections.FIX_PLANS

    def replace_for_run(self, run_id: str, patch_plans: list[PatchPlan]) -> list[PatchPlan]:
        self.collection.delete_many({"run_id": ObjectId(run_id)})
        if not patch_plans:
            return []

        documents = []
        for patch_plan in patch_plans:
            document = patch_plan.model_dump(mode="json")
            document["_id"] = ObjectId(patch_plan.patch_plan_id)
            document["run_id"] = ObjectId(run_id)
            document["issue_group_id"] = ObjectId(patch_plan.issue_group_id)
            documents.append(document)

        self.collection.insert_many(documents)
        return patch_plans

    def list_by_run(self, run_id: str) -> list[PatchPlan]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("priority_rank", 1)
        return [PatchPlan.from_document(document) for document in documents]

    def get_by_id_for_run(self, patch_plan_id: str, run_id: str) -> PatchPlan | None:
        document = self.collection.find_one(
            {"_id": ObjectId(patch_plan_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return PatchPlan.from_document(document)
