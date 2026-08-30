from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.finding import Finding


class FindingRepository(BaseRepository):
    """Repository for normalized diagnostic findings."""

    collection_name = collections.FINDINGS

    def replace_for_run(self, run_id: str, findings: list[Finding]) -> list[Finding]:
        self.collection.delete_many({"run_id": ObjectId(run_id)})
        if not findings:
            return []

        documents = []
        for finding in findings:
            document = finding.model_dump(mode="json")
            document["_id"] = ObjectId(finding.finding_id)
            document["run_id"] = ObjectId(run_id)
            documents.append(document)

        self.collection.insert_many(documents)
        return findings

    def list_by_run(self, run_id: str) -> list[Finding]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [Finding.from_document(document) for document in documents]
