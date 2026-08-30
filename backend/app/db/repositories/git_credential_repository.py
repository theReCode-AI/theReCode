from datetime import UTC, datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.git_credential import GitCredential
from app.models.repository import GitProvider


class GitCredentialNotFoundError(Exception):
    def __init__(self, provider: GitProvider) -> None:
        self.provider = provider
        super().__init__(f"Git credential for provider {provider} not found")


class GitCredentialRepository(BaseRepository):
    """Repository for encrypted Git provider credentials."""

    collection_name = collections.GIT_CREDENTIALS

    def list_by_user(self, user_id: str) -> list[GitCredential]:
        documents = self.collection.find({"user_id": ObjectId(user_id)}).sort("provider", 1)
        return [GitCredential.from_document(document) for document in documents]

    def get_by_user_and_provider(self, user_id: str, provider: GitProvider) -> GitCredential | None:
        document = self.collection.find_one(
            {"user_id": ObjectId(user_id), "provider": provider},
        )
        if document is None:
            return None
        return GitCredential.from_document(document)

    def upsert(
        self,
        user_id: str,
        provider: GitProvider,
        encrypted_token: str,
        token_label: str | None,
    ) -> GitCredential:
        now = datetime.now(UTC)
        document = self.collection.find_one_and_update(
            {"user_id": ObjectId(user_id), "provider": provider},
            {
                "$set": {
                    "encrypted_token": encrypted_token,
                    "token_label": token_label,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": ObjectId(user_id),
                    "provider": provider,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=True,
        )
        if document is None:
            raise DuplicateKeyError("Failed to upsert git credential")
        return GitCredential.from_document(document)

    def delete(self, user_id: str, provider: GitProvider) -> bool:
        result = self.collection.delete_one(
            {"user_id": ObjectId(user_id), "provider": provider},
        )
        return result.deleted_count > 0
