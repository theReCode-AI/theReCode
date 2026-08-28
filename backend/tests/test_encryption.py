import pytest

from app.core.encryption import CredentialEncryptionError, CredentialEncryptor


def test_encrypt_decrypt_roundtrip() -> None:
    encryptor = CredentialEncryptor("test-encryption-key-for-unit-tests")

    encrypted = encryptor.encrypt("ghp_secret_token_value")
    decrypted = encryptor.decrypt(encrypted)

    assert encrypted != "ghp_secret_token_value"
    assert decrypted == "ghp_secret_token_value"


def test_decrypt_invalid_token_raises() -> None:
    encryptor = CredentialEncryptor("test-encryption-key-for-unit-tests")

    with pytest.raises(CredentialEncryptionError):
        encryptor.decrypt("not-valid-ciphertext")
