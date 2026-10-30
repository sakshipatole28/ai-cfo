"""Key-encryption-key (KEK) providers.

A KeyProvider wraps and unwraps tenant data keys. The KEK itself never leaves
the provider: in production that is OpenBao's Transit engine; in development it
is ``LocalKeyProvider`` with keys supplied through the environment.
"""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# AES-GCM nonce size.
NONCE_BYTES = 12
# 256-bit keys.
KEY_BYTES = 32


# Unknown key, or a wrapped key that cannot be opened.
class KeyProviderError(Exception):
    """Raised when a key is unknown or a wrapped key cannot be opened."""


# A data key encrypted under a key-encryption key (KEK); safe to store.
@dataclass(frozen=True)
class WrappedKey:
    """A data key encrypted under a KEK, safe to store in the database."""

    # Which KEK wrapped it (so rotation works).
    key_id: str
    # Random value used once.
    nonce: bytes
    # The encrypted data key.
    ciphertext: bytes

    # Pack into one string for the database.
    def to_token(self) -> str:
        # Encode the nonce.
        nonce = base64.urlsafe_b64encode(self.nonce).decode()
        # Encode the ciphertext.
        ct = base64.urlsafe_b64encode(self.ciphertext).decode()
        # Version, key id, nonce, ciphertext.
        return f"wk1.{self.key_id}.{nonce}.{ct}"

    @classmethod
    # Unpack a stored string.
    def from_token(cls, token: str) -> WrappedKey:
        # Split into the four parts.
        try:
            # The four parts.
            version, key_id, nonce, ct = token.split(".")
        # Wrong number of parts.
        except ValueError as exc:
            # Reject.
            raise KeyProviderError("malformed wrapped key") from exc
        # Only version 1 is known.
        if version != "wk1":
            # Reject.
            raise KeyProviderError(f"unsupported wrapped key version: {version}")
        # Decode back to bytes.
        return cls(
            key_id=key_id,
            nonce=base64.urlsafe_b64decode(nonce),
            ciphertext=base64.urlsafe_b64decode(ct),
        )


# What every key provider offers: wrap and unwrap data keys. The KEK never leaves it.
class KeyProvider(Protocol):
    @property
    # The key id used for new wraps.
    def active_key_id(self) -> str: ...

    # Encrypt a data key.
    def wrap(self, data_key: bytes, *, context: bytes) -> WrappedKey: ...

    # Decrypt a data key.
    def unwrap(self, wrapped: WrappedKey, *, context: bytes) -> bytes: ...


# KEKs held in memory, for development and tests; production uses OpenBao.
class LocalKeyProvider:
    """In-process KEKs for development and tests.

    Supports several KEKs at once so keys can be rotated: new wraps use the
    active key, older wrapped keys still open with their own key id.
    """

    # A keyring of KEKs and which one is active.
    def __init__(self, keks: Mapping[str, bytes], active_key_id: str) -> None:
        # The active key must exist.
        if active_key_id not in keks:
            # Reject.
            raise KeyProviderError(f"active key id {active_key_id!r} not in keyring")
        # Validate every key.
        for key_id, key in keks.items():
            # Ids are used in a dot-separated token.
            if "." in key_id or not key_id:
                # Reject.
                raise KeyProviderError(f"invalid key id {key_id!r}")
            # Keys must be 32 bytes.
            if len(key) != KEY_BYTES:
                # Reject.
                raise KeyProviderError(f"KEK {key_id!r} must be {KEY_BYTES} bytes")
        # Copy the keyring.
        self._keks = dict(keks)
        # Remember the active key.
        self._active = active_key_id

    @classmethod
    # Parse "id:key,id2:key2" from AICFO_LOCAL_KEKS.
    def from_env_value(cls, value: str, active_key_id: str) -> LocalKeyProvider:
        """Parse ``"id1:<base64>,id2:<base64>"``."""
        # Parsed keys.
        keks: dict[str, bytes] = {}
        # Each id:key pair.
        for item in filter(None, (part.strip() for part in value.split(","))):
            # Split at the first colon.
            key_id, _, encoded = item.partition(":")
            # Decode the key.
            keks[key_id] = base64.urlsafe_b64decode(encoded)
        # Build the provider.
        return cls(keks, active_key_id)

    @staticmethod
    # A new random KEK, URL-safe base64.
    def generate_kek() -> str:
        # 32 random bytes.
        return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode()

    @property
    # The active key id.
    def active_key_id(self) -> str:
        # Active key id.
        return self._active

    # Encrypt a data key under the active KEK.
    def wrap(self, data_key: bytes, *, context: bytes) -> WrappedKey:
        # A fresh random nonce each time.
        nonce = os.urandom(NONCE_BYTES)
        # AES-256-GCM encryption; `context` binds the result to its firm.
        ct = AESGCM(self._keks[self._active]).encrypt(nonce, data_key, context)
        # Which key, nonce and ciphertext.
        return WrappedKey(key_id=self._active, nonce=nonce, ciphertext=ct)

    # Decrypt a data key with the KEK it was wrapped under.
    def unwrap(self, wrapped: WrappedKey, *, context: bytes) -> bytes:
        # Find the KEK by id.
        kek = self._keks.get(wrapped.key_id)
        # Unknown key id.
        if kek is None:
            # Reject.
            raise KeyProviderError(f"unknown KEK id {wrapped.key_id!r}")
        # Decrypt.
        try:
            # Fails if the key, nonce, context or data are wrong.
            return AESGCM(kek).decrypt(wrapped.nonce, wrapped.ciphertext, context)
        # Wrong key, wrong firm or tampering.
        except InvalidTag as exc:  # wrong key, wrong context or tampering
            # Reject.
            raise KeyProviderError("wrapped key could not be opened") from exc
