from datetime import UTC, datetime

from bson import ObjectId

from app.core.config import Settings
from app.db.repositories.gemini_credential_repository import (
    GeminiCredentialNotFoundError,
    GeminiCredentialRepository,
)
from app.models.gemini_credential import GeminiCredential
from app.schemas.settings import GeminiCredentialCreate
from app.services.gemini_credential_service import GeminiCredentialService


class InMemoryGeminiCredentialRepository(GeminiCredentialRepository):
    def __init__(self) -> None:
        self._credentials: dict[str, dict] = {}

    def get_by_user(self, user_id: str) -> GeminiCredential | None:
        document = self._credentials.get(user_id)
        if document is None:
            return None
        return GeminiCredential.from_document(document.copy())

    def upsert(
        self,
        user_id: str,
        encrypted_api_key: str,
        key_label: str | None,
    ) -> GeminiCredential:
        now = datetime.now(UTC)
        existing = self._credentials.get(user_id)
        credential_id = existing["_id"] if existing else ObjectId()
        document = {
            "_id": credential_id,
            "user_id": ObjectId(user_id),
            "encrypted_api_key": encrypted_api_key,
            "key_label": key_label,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self._credentials[user_id] = document
        return GeminiCredential.from_document(document.copy())

    def delete(self, user_id: str) -> bool:
        return self._credentials.pop(user_id, None) is not None


def test_gemini_credential_service_prefers_user_key() -> None:
    settings = Settings(
        environment="test",
        credentials_encryption_key="phase5-test-encryption-key-value",
        google_api_key="env-fallback-key",
    )
    service = GeminiCredentialService(InMemoryGeminiCredentialRepository(), settings)
    user_id = str(ObjectId())

    saved = service.save_credential(
        user_id,
        GeminiCredentialCreate(api_key="user-gemini-key", key_label="studio"),
    )
    assert saved.configured is True
    assert saved.key_label == "studio"
    assert service.get_api_key(user_id) == "user-gemini-key"

    service.delete_credential(user_id)
    assert service.get_api_key(user_id) == "env-fallback-key"


def test_gemini_credential_service_raises_when_missing() -> None:
    settings = Settings(
        environment="test",
        credentials_encryption_key="phase5-test-encryption-key-value",
        google_api_key="",
    )
    service = GeminiCredentialService(InMemoryGeminiCredentialRepository(), settings)

    try:
        service.get_api_key(str(ObjectId()))
        raised = False
    except GeminiCredentialNotFoundError:
        raised = True

    assert raised is True
