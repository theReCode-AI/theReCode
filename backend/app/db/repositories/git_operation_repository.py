from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.git_operation import GitOperation


class GitOperationNotFoundError(Exception):
    def __init__(self, git_operation_id: str) -> None:
        self.git_operation_id = git_operation_id
        super().__init__(f"Git operation not found: {git_operation_id}")


class GitOperationRepository(BaseRepository):
    """Repository for persisted git finalization operations."""

    collection_name = collections.GIT_OPERATIONS

    def add(self, operation: GitOperation) -> GitOperation:
        document = operation.model_dump(mode="json")
        document["_id"] = ObjectId(operation.git_operation_id)
        document["run_id"] = ObjectId(operation.run_id)
        document["project_id"] = ObjectId(operation.project_id)
        document["repository_id"] = ObjectId(operation.repository_id)
        self.collection.insert_one(document)
        return operation

    def list_by_run(self, run_id: str) -> list[GitOperation]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [GitOperation.from_document(document) for document in documents]

    def get_by_id_for_run(self, git_operation_id: str, run_id: str) -> GitOperation | None:
        document = self.collection.find_one(
            {"_id": ObjectId(git_operation_id), "run_id": ObjectId(run_id)},
        )
        if document is None:
            return None
        return GitOperation.from_document(document)
