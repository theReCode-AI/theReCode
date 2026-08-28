from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.peer_review_result import PeerReviewResult


class PeerReviewResultNotFoundError(Exception):
    def __init__(self, peer_review_id: str) -> None:
        self.peer_review_id = peer_review_id
        super().__init__(f"Peer review result not found: {peer_review_id}")


class PeerReviewResultRepository(BaseRepository):
    """Repository for persisted peer review results."""

    collection_name = collections.REVIEWS

    def add(self, result: PeerReviewResult) -> PeerReviewResult:
        document = result.model_dump(mode="json")
        document["_id"] = ObjectId(result.peer_review_id)
        document["run_id"] = ObjectId(result.run_id)
        document["patch_plan_id"] = ObjectId(result.patch_plan_id)
        document["fix_attempt_id"] = ObjectId(result.fix_attempt_id)
        document["verification_result_id"] = ObjectId(result.verification_result_id)
        document["regression_test_id"] = ObjectId(result.regression_test_id)
        self.collection.insert_one(document)
        return result

    def list_by_run(self, run_id: str) -> list[PeerReviewResult]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [PeerReviewResult.from_document(document) for document in documents]

    def get_by_id_for_run(self, peer_review_id: str, run_id: str) -> PeerReviewResult | None:
        document = self.collection.find_one(
            {"_id": ObjectId(peer_review_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return PeerReviewResult.from_document(document)
