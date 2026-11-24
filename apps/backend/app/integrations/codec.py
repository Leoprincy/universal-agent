"""Credential encryption codec — fails closed when no key is configured.

Uses Fernet (AES-128-CBC + HMAC) from the ``cryptography`` package. The key
must be supplied via ``UGA_CREDENTIAL_ENCRYPTION_KEY`` as a valid Fernet key
(urlsafe-base64-encoded 32 bytes). Generate one with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If the key is missing or malformed, every encrypt/decrypt operation raises
``CredentialConfigError`` — credentials are never stored or returned in
plaintext and there is no insecure fallback.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class CredentialConfigError(RuntimeError):
    """Raised when credential encryption is not configured or fails."""


class CredentialCodec:
    KEY_VERSION = 1

    def __init__(self, key: str | None) -> None:
        if not key:
            raise CredentialConfigError(
                "UGA_CREDENTIAL_ENCRYPTION_KEY is not configured; credential storage is disabled"
            )
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise CredentialConfigError(
                "UGA_CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise CredentialConfigError(
                "Stored credential cannot be decrypted with the configured key"
            ) from exc
