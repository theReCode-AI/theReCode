from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.fix_attempt import FixAttempt


class FixAttemptNotFoundError(Exception):
    def __init__(self, fix_attempt_id: str) -> None:
        self.fix_attempt_id = fix_attempt_id
        super().__init__(f"Fix attempt not found: {fix_attempt_id}")


class FixAttemptRepository(BaseRepository):
    """Repository for persisted fix attempts."""

    collection_name = collections.FIX_ATTEMPTS

    def add(self, fix_attempt: FixAttempt) -> FixAttempt:
        document = fix_attempt.model_dump(mode="json")
        document["_id"] = ObjectId(fix_attempt.fix_attempt_id)
        document["run_id"] = ObjectId(fix_attempt.run_id)
        document["patch_plan_id"] = ObjectId(fix_attempt.patch_plan_id)
        self.collection.insert_one(document)
        return fix_attempt

    def list_by_run(self, run_id: str) -> list[FixAttempt]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [FixAttempt.from_document(document) for document in documents]

    def count_by_patch_plan(self, run_id: str, patch_plan_id: str) -> int:
        return self.collection.count_documents(
            {
                "run_id": ObjectId(run_id),
                "patch_plan_id": ObjectId(patch_plan_id),
            },
        )

    def get_by_id_for_run(self, fix_attempt_id: str, run_id: str) -> FixAttempt | None:
        document = self.collection.find_one(
            {"_id": ObjectId(fix_attempt_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return FixAttempt.from_document(document)
