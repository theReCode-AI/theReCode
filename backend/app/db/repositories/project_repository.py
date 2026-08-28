from datetime import UTC, datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.project import Project


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project {project_id} not found")


class ProjectNameExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Project name {name} already exists for user")


class ProjectRepository(BaseRepository):
    """Repository for project persistence."""

    collection_name = collections.PROJECTS

    def list_by_user(self, user_id: str) -> list[Project]:
        documents = self.collection.find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
        return [Project.from_document(document) for document in documents]

    def get_by_id_for_user(self, project_id: str, user_id: str) -> Project | None:
        if not ObjectId.is_valid(project_id):
            return None

        document = self.collection.find_one(
            {"_id": ObjectId(project_id), "user_id": ObjectId(user_id)},
        )
        if document is None:
            return None
        return Project.from_document(document)

    def create(self, user_id: str, name: str, description: str | None) -> Project:
        now = datetime.now(UTC)
        document = {
            "user_id": ObjectId(user_id),
            "name": name.strip(),
            "description": description,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise ProjectNameExistsError(name) from exc

        document["_id"] = result.inserted_id
        return Project.from_document(document)

    def update(
        self,
        project_id: str,
        user_id: str,
        name: str | None,
        description: str | None | object = ...,
    ) -> Project | None:
        if not ObjectId.is_valid(project_id):
            return None

        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if name is not None:
            updates["name"] = name.strip()
        if description is not ...:
            updates["description"] = description

        try:
            document = self.collection.find_one_and_update(
                {"_id": ObjectId(project_id), "user_id": ObjectId(user_id)},
                {"$set": updates},
                return_document=True,
            )
        except DuplicateKeyError as exc:
            raise ProjectNameExistsError(name or "") from exc

        if document is None:
            return None
        return Project.from_document(document)

    def delete(self, project_id: str, user_id: str) -> bool:
        if not ObjectId.is_valid(project_id):
            return False

        result = self.collection.delete_one(
            {"_id": ObjectId(project_id), "user_id": ObjectId(user_id)},
        )
        return result.deleted_count > 0
