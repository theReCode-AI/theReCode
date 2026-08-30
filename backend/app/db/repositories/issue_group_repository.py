from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.issue_group import IssueGroup


class IssueGroupRepository(BaseRepository):
    """Repository for correlated issue groups."""

    collection_name = collections.ISSUE_GROUPS

    def replace_for_run(self, run_id: str, issue_groups: list[IssueGroup]) -> list[IssueGroup]:
        self.collection.delete_many({"run_id": ObjectId(run_id)})
        if not issue_groups:
            return []

        documents = []
        for issue_group in issue_groups:
            document = issue_group.model_dump(mode="json")
            document["_id"] = ObjectId(issue_group.issue_group_id)
            document["run_id"] = ObjectId(run_id)
            documents.append(document)

        self.collection.insert_many(documents)
        return issue_groups

    def list_by_run(self, run_id: str) -> list[IssueGroup]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("priority_rank", 1)
        return [IssueGroup.from_document(document) for document in documents]
