from app.core.config import Settings
from app.core.encryption import CredentialEncryptor
from app.core.logging import get_logger
from app.db.repositories.git_credential_repository import (
    GitCredentialNotFoundError,
    GitCredentialRepository,
)
from app.models.git_credential import GitCredential
from app.models.repository import GitProvider
from app.schemas.git import GitCredentialCreate, GitCredentialResponse

logger = get_logger(__name__)


class GitCredentialService:
    """Manage encrypted Git provider credentials."""

    def __init__(
        self,
        credential_repository: GitCredentialRepository,
        app_settings: Settings,
    ) -> None:
        self._credential_repository = credential_repository
        self._encryptor = CredentialEncryptor(app_settings.credentials_encryption_key)

    def save_credential(self, user_id: str, payload: GitCredentialCreate) -> GitCredentialResponse:
        encrypted_token = self._encryptor.encrypt(payload.access_token)
        credential = self._credential_repository.upsert(
            user_id=user_id,
            provider=payload.provider,
            encrypted_token=encrypted_token,
            token_label=payload.token_label,
        )
        logger.info(
            "Git credential saved",
            extra={
                "user_id": user_id,
                "provider": payload.provider,
                "stage": "git_credential_save",
            },
        )
        return self._to_response(credential)

    def list_credentials(self, user_id: str) -> list[GitCredentialResponse]:
        credentials = self._credential_repository.list_by_user(user_id)
        return [self._to_response(credential) for credential in credentials]

    def delete_credential(self, user_id: str, provider: GitProvider) -> None:
        deleted = self._credential_repository.delete(user_id, provider)
        if not deleted:
            raise GitCredentialNotFoundError(provider)

        logger.info(
            "Git credential deleted",
            extra={"user_id": user_id, "provider": provider, "stage": "git_credential_delete"},
        )

    def get_access_token(self, user_id: str, provider: GitProvider) -> str:
        credential = self._credential_repository.get_by_user_and_provider(user_id, provider)
        if credential is None:
            raise GitCredentialNotFoundError(provider)
        return self._encryptor.decrypt(credential.encrypted_token)

    @staticmethod
    def _to_response(credential: GitCredential) -> GitCredentialResponse:
        return GitCredentialResponse(
            id=credential.id,
            provider=credential.provider,
            token_label=credential.token_label,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )
