import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionError(Exception):
    pass


class CredentialEncryptor:
    """Encrypt and decrypt provider credentials at rest."""

    def __init__(self, encryption_key: str) -> None:
        self._fernet = Fernet(self._derive_fernet_key(encryption_key))

    @staticmethod
    def _derive_fernet_key(encryption_key: str) -> bytes:
        digest = hashlib.sha256(encryption_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            value = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken as exc:
            raise CredentialEncryptionError("Failed to decrypt credential") from exc
        return value.decode("utf-8")
