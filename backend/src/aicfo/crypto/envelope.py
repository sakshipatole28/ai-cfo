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

# Format version of sealed fields.
_FIELD_VERSION = "f1"


# Malformed, tampered with, or used in the wrong place.
class DecryptionError(Exception):
    """Ciphertext is malformed, tampered with, or bound to a different context."""


# Binds a wrapped key to its firm.
def _wrap_context(tenant_id: str) -> bytes:
    # Used as authenticated data when wrapping.
    return f"aicfo:tenant-data-key:{tenant_id}".encode()


# Seals and opens field values for exactly one firm.
class TenantCipher:
    """Seals and opens field values for exactly one tenant."""

    # Hold the firm's data key.
    def __init__(self, tenant_id: str, data_key: bytes) -> None:
        # Must be 32 bytes.
        if len(data_key) != KEY_BYTES:
            # Reject.
            raise ValueError("data key must be 32 bytes")
        # The firm.
        self.tenant_id = tenant_id
        # AES-256-GCM with the data key.
        self._aead = AESGCM(data_key)

    @classmethod
    # New firm: make a data key and wrap it.
    def create(cls, provider: KeyProvider, tenant_id: str) -> tuple[TenantCipher, WrappedKey]:
        """Create a new tenant data key. Store only the returned ``WrappedKey``."""
        # A random 256-bit key.
        data_key = AESGCM.generate_key(bit_length=256)
        # Encrypt it under the KEK; this is what gets stored.
        wrapped = provider.wrap(data_key, context=_wrap_context(tenant_id))
        # The cipher (for now) and the wrapped key (to store).
        return cls(tenant_id, data_key), wrapped

    @classmethod
    # Existing firm: unwrap the stored key.
    def open(cls, provider: KeyProvider, tenant_id: str, wrapped: WrappedKey) -> TenantCipher:
        # Decrypt the data key.
        data_key = provider.unwrap(wrapped, context=_wrap_context(tenant_id))
        # The cipher.
        return cls(tenant_id, data_key)

    # Associated data: ties a ciphertext to its firm and place.
    def _aad(self, aad: str) -> bytes:
        # Firm and location.
        return f"{self.tenant_id}|{aad}".encode()

    # Encrypt a value.
    def seal(self, plaintext: bytes, *, aad: str) -> str:
        # Fresh random nonce each time.
        nonce = os.urandom(NONCE_BYTES)
        # AES-GCM encrypt; also protects against tampering.
        ct = self._aead.encrypt(nonce, plaintext, self._aad(aad))
        # Version, nonce and ciphertext as one string.
        return ".".join(
            (
                _FIELD_VERSION,
                base64.urlsafe_b64encode(nonce).decode(),
                base64.urlsafe_b64encode(ct).decode(),
            )
        )

    # Decrypt a value.
    def open_field(self, token: str, *, aad: str) -> bytes:
        # Unpack and decrypt.
        try:
            # The three parts.
            version, nonce_b64, ct_b64 = token.split(".")
            # Unknown format.
            if version != _FIELD_VERSION:
                # Reject.
                raise DecryptionError(f"unsupported field version: {version}")
            # Decode the nonce.
            nonce = base64.urlsafe_b64decode(nonce_b64)
            # Decode the ciphertext.
            ct = base64.urlsafe_b64decode(ct_b64)
            # Fails if the data or its place were changed.
            return self._aead.decrypt(nonce, ct, self._aad(aad))
        # Our own error…
        except DecryptionError:
            # …passes through.
            raise
        # Malformed or tampered…
        except (ValueError, InvalidTag) as exc:
            # …becomes one clear error.
            raise DecryptionError("field could not be decrypted") from exc


# Rotation: re-encrypt the small data key under the newest KEK; the data is untouched.
def rewrap(provider: KeyProvider, tenant_id: str, wrapped: WrappedKey) -> WrappedKey:
    """Re-wrap a tenant data key under the provider's currently active KEK."""
    # Same firm binding.
    context = _wrap_context(tenant_id)
    # Unwrap with the old KEK, wrap with the new.
    return provider.wrap(provider.unwrap(wrapped, context=context), context=context)
