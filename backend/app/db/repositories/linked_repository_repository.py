from datetime import UTC, datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.repository import GitProvider, Repository


class LinkedRepositoryNotFoundError(Exception):
    def __init__(self, repository_id: str) -> None:
        self.repository_id = repository_id
        super().__init__(f"Repository {repository_id} not found")


class LinkedRepositoryExistsError(Exception):
    def __init__(self, full_name: str, provider: GitProvider) -> None:
        self.full_name = full_name
        self.provider = provider
        super().__init__(f"Repository {full_name} already linked for provider {provider}")


class LinkedRepositoryRepository(BaseRepository):
    """Repository for linked Git repository persistence."""

    collection_name = collections.REPOSITORIES

    def list_by_project(self, project_id: str) -> list[Repository]:
        documents = self.collection.find({"project_id": ObjectId(project_id)}).sort(
            "created_at",
            -1,
        )
        return [Repository.from_document(document) for document in documents]

    def get_by_id_for_project(self, repository_id: str, project_id: str) -> Repository | None:
        if not ObjectId.is_valid(repository_id) or not ObjectId.is_valid(project_id):
            return None

        document = self.collection.find_one(
            {
                "_id": ObjectId(repository_id),
                "project_id": ObjectId(project_id),
            },
        )
        if document is None:
            return None
        return Repository.from_document(document)

    def create(
        self,
        project_id: str,
        provider: GitProvider,
        full_name: str,
        default_branch: str,
        clone_url: str | None,
    ) -> Repository:
        now = datetime.now(UTC)
        document = {
            "project_id": ObjectId(project_id),
            "provider": provider,
            "full_name": full_name.strip(),
            "default_branch": default_branch.strip(),
            "clone_url": clone_url,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise LinkedRepositoryExistsError(full_name, provider) from exc

        document["_id"] = result.inserted_id
        return Repository.from_document(document)

    def update(
        self,
        repository_id: str,
        project_id: str,
        default_branch: str | None,
        clone_url: str | None | object = ...,
    ) -> Repository | None:
        if not ObjectId.is_valid(repository_id) or not ObjectId.is_valid(project_id):
            return None

        updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if default_branch is not None:
            updates["default_branch"] = default_branch.strip()
        if clone_url is not ...:
            updates["clone_url"] = clone_url

        document = self.collection.find_one_and_update(
            {
                "_id": ObjectId(repository_id),
                "project_id": ObjectId(project_id),
            },
            {"$set": updates},
            return_document=True,
        )
        if document is None:
            return None
        return Repository.from_document(document)

    def delete(self, repository_id: str, project_id: str) -> bool:
        if not ObjectId.is_valid(repository_id) or not ObjectId.is_valid(project_id):
            return False

        result = self.collection.delete_one(
            {
                "_id": ObjectId(repository_id),
                "project_id": ObjectId(project_id),
            },
        )
        return result.deleted_count > 0

    def delete_by_project(self, project_id: str) -> int:
        if not ObjectId.is_valid(project_id):
            return 0

        result = self.collection.delete_many({"project_id": ObjectId(project_id)})
        return result.deleted_count
