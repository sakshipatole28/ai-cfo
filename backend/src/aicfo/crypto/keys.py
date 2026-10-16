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

NONCE_BYTES = 12
KEY_BYTES = 32


class KeyProviderError(Exception):
    """Raised when a key is unknown or a wrapped key cannot be opened."""


@dataclass(frozen=True)
class WrappedKey:
    """A data key encrypted under a KEK, safe to store in the database."""

    key_id: str
    nonce: bytes
    ciphertext: bytes

    def to_token(self) -> str:
        nonce = base64.urlsafe_b64encode(self.nonce).decode()
        ct = base64.urlsafe_b64encode(self.ciphertext).decode()
        return f"wk1.{self.key_id}.{nonce}.{ct}"

    @classmethod
    def from_token(cls, token: str) -> WrappedKey:
        try:
            version, key_id, nonce, ct = token.split(".")
        except ValueError as exc:
            raise KeyProviderError("malformed wrapped key") from exc
        if version != "wk1":
            raise KeyProviderError(f"unsupported wrapped key version: {version}")
        return cls(
            key_id=key_id,
            nonce=base64.urlsafe_b64decode(nonce),
            ciphertext=base64.urlsafe_b64decode(ct),
        )


class KeyProvider(Protocol):
    @property
    def active_key_id(self) -> str: ...

    def wrap(self, data_key: bytes, *, context: bytes) -> WrappedKey: ...

    def unwrap(self, wrapped: WrappedKey, *, context: bytes) -> bytes: ...


class LocalKeyProvider:
    """In-process KEKs for development and tests.

    Supports several KEKs at once so keys can be rotated: new wraps use the
    active key, older wrapped keys still open with their own key id.
    """

    def __init__(self, keks: Mapping[str, bytes], active_key_id: str) -> None:
        if active_key_id not in keks:
            raise KeyProviderError(f"active key id {active_key_id!r} not in keyring")
        for key_id, key in keks.items():
            if "." in key_id or not key_id:
                raise KeyProviderError(f"invalid key id {key_id!r}")
            if len(key) != KEY_BYTES:
                raise KeyProviderError(f"KEK {key_id!r} must be {KEY_BYTES} bytes")
        self._keks = dict(keks)
        self._active = active_key_id

    @classmethod
    def from_env_value(cls, value: str, active_key_id: str) -> LocalKeyProvider:
        """Parse ``"id1:<base64>,id2:<base64>"``."""
        keks: dict[str, bytes] = {}
        for item in filter(None, (part.strip() for part in value.split(","))):
            key_id, _, encoded = item.partition(":")
            keks[key_id] = base64.urlsafe_b64decode(encoded)
        return cls(keks, active_key_id)

    @staticmethod
    def generate_kek() -> str:
        return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode()

    @property
    def active_key_id(self) -> str:
        return self._active

    def wrap(self, data_key: bytes, *, context: bytes) -> WrappedKey:
        nonce = os.urandom(NONCE_BYTES)
        ct = AESGCM(self._keks[self._active]).encrypt(nonce, data_key, context)
        return WrappedKey(key_id=self._active, nonce=nonce, ciphertext=ct)

    def unwrap(self, wrapped: WrappedKey, *, context: bytes) -> bytes:
        kek = self._keks.get(wrapped.key_id)
        if kek is None:
            raise KeyProviderError(f"unknown KEK id {wrapped.key_id!r}")
        try:
            return AESGCM(kek).decrypt(wrapped.nonce, wrapped.ciphertext, context)
        except InvalidTag as exc:  # wrong key, wrong context or tampering
            raise KeyProviderError("wrapped key could not be opened") from exc
