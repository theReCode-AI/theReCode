from app.core.config import Settings
from app.core.encryption import CredentialEncryptor
from app.core.logging import get_logger
from app.db.repositories.gemini_credential_repository import (
    GeminiCredentialNotFoundError,
    GeminiCredentialRepository,
)
from app.google_adk.bootstrap import resolve_api_key
from app.models.gemini_credential import GeminiCredential
from app.schemas.settings import GeminiCredentialCreate, GeminiCredentialResponse

logger = get_logger(__name__)


class GeminiCredentialService:
    """Manage encrypted per-user Gemini API keys."""

    def __init__(
        self,
        credential_repository: GeminiCredentialRepository,
        app_settings: Settings,
    ) -> None:
        self._credential_repository = credential_repository
        self._app_settings = app_settings
        self._encryptor = CredentialEncryptor(app_settings.credentials_encryption_key)

    def save_credential(
        self,
        user_id: str,
        payload: GeminiCredentialCreate,
    ) -> GeminiCredentialResponse:
        encrypted_api_key = self._encryptor.encrypt(payload.api_key.strip())
        credential = self._credential_repository.upsert(
            user_id=user_id,
            encrypted_api_key=encrypted_api_key,
            key_label=payload.key_label,
        )
        logger.info(
            "Gemini credential saved",
            extra={"user_id": user_id, "stage": "gemini_credential_save"},
        )
        return self._to_response(credential)

    def get_credential(self, user_id: str) -> GeminiCredentialResponse | None:
        credential = self._credential_repository.get_by_user(user_id)
        if credential is None:
            return None
        return self._to_response(credential)

    def delete_credential(self, user_id: str) -> None:
        deleted = self._credential_repository.delete(user_id)
        if not deleted:
            raise GeminiCredentialNotFoundError()
        logger.info(
            "Gemini credential deleted",
            extra={"user_id": user_id, "stage": "gemini_credential_delete"},
        )

    def get_api_key(self, user_id: str) -> str:
        """Return the user's Gemini key, falling back to server env config."""
        credential = self._credential_repository.get_by_user(user_id)
        if credential is not None:
            return self._encryptor.decrypt(credential.encrypted_api_key)

        fallback = resolve_api_key(self._app_settings)
        if fallback:
            return fallback
        raise GeminiCredentialNotFoundError()

    def try_get_api_key(self, user_id: str) -> str | None:
        try:
            return self.get_api_key(user_id)
        except GeminiCredentialNotFoundError:
            return None

    @staticmethod
    def _to_response(credential: GeminiCredential) -> GeminiCredentialResponse:
        return GeminiCredentialResponse(
            id=credential.id,
            configured=True,
            key_label=credential.key_label,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )
