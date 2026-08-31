from datetime import UTC, datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db import collections
from app.db.repositories.base import BaseRepository
from app.models.gemini_credential import GeminiCredential


class GeminiCredentialNotFoundError(Exception):
    def __init__(self) -> None:
        super().__init__("Gemini API key is not configured for this user")


class GeminiCredentialRepository(BaseRepository):
    """Repository for encrypted per-user Gemini API keys."""

    collection_name = collections.GEMINI_CREDENTIALS

    def get_by_user(self, user_id: str) -> GeminiCredential | None:
        document = self.collection.find_one({"user_id": ObjectId(user_id)})
        if document is None:
            return None
        return GeminiCredential.from_document(document)

    def upsert(
        self,
        user_id: str,
        encrypted_api_key: str,
        key_label: str | None,
    ) -> GeminiCredential:
        now = datetime.now(UTC)
        document = self.collection.find_one_and_update(
            {"user_id": ObjectId(user_id)},
            {
                "$set": {
                    "encrypted_api_key": encrypted_api_key,
                    "key_label": key_label,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "user_id": ObjectId(user_id),
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=True,
        )
        if document is None:
            raise DuplicateKeyError("Failed to upsert Gemini credential")
        return GeminiCredential.from_document(document)

    def delete(self, user_id: str) -> bool:
        result = self.collection.delete_one({"user_id": ObjectId(user_id)})
        return result.deleted_count > 0
