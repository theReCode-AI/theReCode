from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.verification_result import VerificationResult


class VerificationResultNotFoundError(Exception):
    def __init__(self, verification_result_id: str) -> None:
        self.verification_result_id = verification_result_id
        super().__init__(f"Verification result not found: {verification_result_id}")


class VerificationResultRepository(BaseRepository):
    """Repository for persisted verification results."""

    collection_name = collections.VERIFICATION_RESULTS

    def add(self, verification_result: VerificationResult) -> VerificationResult:
        document = verification_result.model_dump(mode="json")
        document["_id"] = ObjectId(verification_result.verification_result_id)
        document["run_id"] = ObjectId(verification_result.run_id)
        document["fix_attempt_id"] = ObjectId(verification_result.fix_attempt_id)
        document["patch_plan_id"] = ObjectId(verification_result.patch_plan_id)
        self.collection.insert_one(document)
        return verification_result

    def list_by_run(self, run_id: str) -> list[VerificationResult]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [VerificationResult.from_document(document) for document in documents]

    def get_by_id_for_run(
        self,
        verification_result_id: str,
        run_id: str,
    ) -> VerificationResult | None:
        document = self.collection.find_one(
            {"_id": ObjectId(verification_result_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return VerificationResult.from_document(document)
