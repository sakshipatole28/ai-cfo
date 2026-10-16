"""Envelope encryption for tenant data (Portfolio Store).

Hierarchy:  KEK (KeyProvider / OpenBao)  →  tenant data key  →  field ciphertext.

* Each tenant has one random 256-bit data key, stored only in wrapped form.
* Fields are sealed with AES-256-GCM. The associated data binds every
  ciphertext to its tenant and location (e.g. ``holdings:<id>:units``), so a
  ciphertext copied to another row or tenant fails to open.
* Crypto-shredding: deleting a tenant's wrapped key makes all of its data
  permanently unreadable.
* KEK rotation: ``rewrap`` re-encrypts only the small wrapped key, not the data.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aicfo.crypto.keys import KEY_BYTES, NONCE_BYTES, KeyProvider, WrappedKey

_FIELD_VERSION = "f1"


class DecryptionError(Exception):
    """Ciphertext is malformed, tampered with, or bound to a different context."""


def _wrap_context(tenant_id: str) -> bytes:
    return f"aicfo:tenant-data-key:{tenant_id}".encode()


class TenantCipher:
    """Seals and opens field values for exactly one tenant."""

    def __init__(self, tenant_id: str, data_key: bytes) -> None:
        if len(data_key) != KEY_BYTES:
            raise ValueError("data key must be 32 bytes")
        self.tenant_id = tenant_id
        self._aead = AESGCM(data_key)

    @classmethod
    def create(cls, provider: KeyProvider, tenant_id: str) -> tuple[TenantCipher, WrappedKey]:
        """Create a new tenant data key. Store only the returned ``WrappedKey``."""
        data_key = AESGCM.generate_key(bit_length=256)
        wrapped = provider.wrap(data_key, context=_wrap_context(tenant_id))
        return cls(tenant_id, data_key), wrapped

    @classmethod
    def open(cls, provider: KeyProvider, tenant_id: str, wrapped: WrappedKey) -> TenantCipher:
        data_key = provider.unwrap(wrapped, context=_wrap_context(tenant_id))
        return cls(tenant_id, data_key)

    def _aad(self, aad: str) -> bytes:
        return f"{self.tenant_id}|{aad}".encode()

    def seal(self, plaintext: bytes, *, aad: str) -> str:
        nonce = os.urandom(NONCE_BYTES)
        ct = self._aead.encrypt(nonce, plaintext, self._aad(aad))
        return ".".join(
            (
                _FIELD_VERSION,
                base64.urlsafe_b64encode(nonce).decode(),
                base64.urlsafe_b64encode(ct).decode(),
            )
        )

    def open_field(self, token: str, *, aad: str) -> bytes:
        try:
            version, nonce_b64, ct_b64 = token.split(".")
            if version != _FIELD_VERSION:
                raise DecryptionError(f"unsupported field version: {version}")
            nonce = base64.urlsafe_b64decode(nonce_b64)
            ct = base64.urlsafe_b64decode(ct_b64)
            return self._aead.decrypt(nonce, ct, self._aad(aad))
        except DecryptionError:
            raise
        except (ValueError, InvalidTag) as exc:
            raise DecryptionError("field could not be decrypted") from exc


def rewrap(provider: KeyProvider, tenant_id: str, wrapped: WrappedKey) -> WrappedKey:
    """Re-wrap a tenant data key under the provider's currently active KEK."""
    context = _wrap_context(tenant_id)
    return provider.wrap(provider.unwrap(wrapped, context=context), context=context)
