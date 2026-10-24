"""SecretBox: the secrets sealed with AES-GCM under a key derived from SHELFDROP_SECRET_KEY
(ADR 0012). The name of a secret is its associated data: a sealed value moved to another name
does not open."""

import secrets
from collections.abc import Sequence
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from shelfdrop.settings.exceptions import SecretUnreadableError

NONCE_BYTES: Final = 12
# Changing it makes every sealed secret unreadable.
KEY_INFO: Final = b"shelfdrop secrets v1"


class SecretBox:
    def __init__(self, secret_key: str) -> None:
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=KEY_INFO).derive(
            secret_key.encode()
        )
        self.aead = AESGCM(key)

    def seal(self, name: str, value: str) -> bytes:
        """A random nonce, then the ciphertext and its tag."""
        nonce = secrets.token_bytes(NONCE_BYTES)
        return nonce + self.aead.encrypt(nonce, value.encode(), name.encode())

    def open(self, name: str, sealed: bytes) -> str:
        """Raises SecretUnreadableError when the key or the name differ, or the value changed."""
        try:
            plain = self.aead.decrypt(sealed[:NONCE_BYTES], sealed[NONCE_BYTES:], name.encode())
        except (InvalidTag, ValueError) as exc:
            raise SecretUnreadableError(name) from exc
        return plain.decode()

    def open_any(self, names: Sequence[str], sealed: bytes) -> str:
        """The value sealed under the first of `names` that opens it (a secret moved to another
        name opens under its former one). Raises SecretUnreadableError when none does."""
        for name in names[:-1]:
            try:
                return self.open(name, sealed)
            except SecretUnreadableError:
                continue
        return self.open(names[-1], sealed)
