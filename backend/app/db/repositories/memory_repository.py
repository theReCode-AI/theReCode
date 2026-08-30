from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.memory_entry import MemoryEntry


class MemoryNotFoundError(Exception):
    def __init__(self, memory_id: str) -> None:
        self.memory_id = memory_id
        super().__init__(f"Memory entry not found: {memory_id}")


class MemoryRepository(BaseRepository):
    """Repository for persisted project memories."""

    collection_name = collections.MEMORIES

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        document = entry.model_dump(mode="json")
        document["_id"] = ObjectId(entry.memory_id)
        document["project_id"] = ObjectId(entry.project_id)
        document["run_id"] = ObjectId(entry.run_id)
        self.collection.insert_one(document)
        return entry

    def list_by_project(self, project_id: str) -> list[MemoryEntry]:
        documents = self.collection.find({"project_id": ObjectId(project_id)}).sort("created_at", 1)
        return [MemoryEntry.from_document(document) for document in documents]

    def list_by_run(self, run_id: str) -> list[MemoryEntry]:
        documents = self.collection.find({"run_id": ObjectId(run_id)}).sort("created_at", 1)
        return [MemoryEntry.from_document(document) for document in documents]

    def get_by_id_for_project(self, memory_id: str, project_id: str) -> MemoryEntry | None:
        document = self.collection.find_one(
            {"_id": ObjectId(memory_id), "project_id": ObjectId(project_id)},
        )
        if document is None:
            return None
        return MemoryEntry.from_document(document)

    def delete_by_run_and_source_keys(self, run_id: str, source_keys: list[str]) -> None:
        if not source_keys:
            return
        self.collection.delete_many(
            {"run_id": ObjectId(run_id), "source_key": {"$in": source_keys}},
        )
