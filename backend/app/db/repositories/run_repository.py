from datetime import UTC, datetime

from bson import ObjectId

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.project_intelligence import ProjectIntelligence
from app.models.run import Run, RunStatus


class RunNotFoundError(Exception):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run {run_id} not found")


class RunRepository(BaseRepository):
    """Repository for autonomous run persistence."""

    collection_name = collections.RUNS

    def get_by_id_for_user(self, run_id: str, user_id: str) -> Run | None:
        if not ObjectId.is_valid(run_id):
            return None

        document = self.collection.find_one(
            {"_id": ObjectId(run_id), "user_id": ObjectId(user_id)},
        )
        if document is None:
            return None
        return Run.from_document(document)

    def list_by_project(self, project_id: str, user_id: str) -> list[Run]:
        documents = self.collection.find(
            {"project_id": ObjectId(project_id), "user_id": ObjectId(user_id)},
        ).sort("created_at", -1)
        return [Run.from_document(document) for document in documents]

    def create(
        self,
        run_id: str,
        project_id: str,
        user_id: str,
        repository_id: str | None,
        workspace_path: str,
        status: RunStatus = RunStatus.CREATED,
    ) -> Run:
        now = datetime.now(UTC)
        document = {
            "_id": ObjectId(run_id),
            "project_id": ObjectId(project_id),
            "user_id": ObjectId(user_id),
            "repository_id": ObjectId(repository_id) if repository_id else None,
            "status": status.value,
            "workspace_path": workspace_path,
            "created_at": now,
            "updated_at": now,
        }
        self.collection.insert_one(document)
        return Run.from_document(document)

    def update_status(self, run_id: str, user_id: str, status: RunStatus) -> Run | None:
        if not ObjectId.is_valid(run_id):
            return None

        document = self.collection.find_one_and_update(
            {"_id": ObjectId(run_id), "user_id": ObjectId(user_id)},
            {"$set": {"status": status.value, "updated_at": datetime.now(UTC)}},
            return_document=True,
        )
        if document is None:
            return None
        return Run.from_document(document)

    def update_project_intelligence(
        self,
        run_id: str,
        user_id: str,
        intelligence: ProjectIntelligence,
        status: RunStatus,
    ) -> Run | None:
        if not ObjectId.is_valid(run_id):
            return None

        now = datetime.now(UTC)
        document = self.collection.find_one_and_update(
            {"_id": ObjectId(run_id), "user_id": ObjectId(user_id)},
            {
                "$set": {
                    "project_intelligence": intelligence.model_dump(mode="json"),
                    "analyzed_at": now,
                    "status": status.value,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if document is None:
            return None
        return Run.from_document(document)
