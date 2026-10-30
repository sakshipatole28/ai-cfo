"""Authenticator-app codes (TOTP, RFC 6238) with secrets encrypted per firm.

The TOTP secret is sealed with the firm's data key (envelope encryption, `aicfo.crypto`), so a
database dump alone cannot generate anyone's codes.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pyotp

from aicfo.config import get_settings
from aicfo.crypto import KeyProvider, LocalKeyProvider, TenantCipher, WrappedKey

log = logging.getLogger(__name__)
# Name shown in the authenticator app.
ISSUER = "AI CFO"  # the name shown in the authenticator app


# Create the key provider once.
@lru_cache
# Where the key-encryption key comes from.
def key_provider() -> KeyProvider:
    """Key-encryption keys from AICFO_LOCAL_KEKS (dev/test). Production swaps in OpenBao."""
    # Settings.
    s = get_settings()
    # AICFO_LOCAL_KEKS, e.g. "k1:<key>".
    value = s.local_keks.get_secret_value() if s.local_keks else ""
    # A real configured key…
    if value and "REPLACE_ME" not in value:
        # …is used.
        return LocalKeyProvider.from_env_value(value, s.active_kek_id)  # configured keys
    # Development without a key: make a throwaway one.
    if s.env in ("dev", "test"):
        # Warn: accounts end when the server restarts.
        log.warning("AICFO_LOCAL_KEKS not set: using a temporary key (accounts end on restart)")
        # Throwaway key.
        return LocalKeyProvider.from_env_value(
            f"{s.active_kek_id}:{LocalKeyProvider.generate_kek()}", s.active_kek_id
        )
    # Outside dev/test a real key is mandatory.
    raise RuntimeError("AICFO_LOCAL_KEKS must be set outside dev/test")


# Make a fresh data key for a new firm.
def new_firm_key(tenant_id: str) -> tuple[TenantCipher, str]:
    """A fresh data key for a new firm: the cipher to use now and the wrapped key to store."""
    # The key (kept in memory) and its wrapped copy (stored).
    cipher, wrapped = TenantCipher.create(key_provider(), tenant_id)
    # Only the wrapped copy is saved.
    return cipher, wrapped.to_token()


# Reopen a firm's data key from its stored wrapped copy.
def firm_cipher(tenant_id: str, wrapped_token: str) -> TenantCipher:
    """Open a firm's cipher from its stored wrapped data key."""
    # Unwrap with the key-encryption key.
    return TenantCipher.open(key_provider(), tenant_id, WrappedKey.from_token(wrapped_token))


# A random authenticator secret.
def new_secret() -> str:
    """A random base32 TOTP secret (160 bits)."""
    # 160 random bits, base32.
    return pyotp.random_base32(32)


# Encrypt a user's authenticator secret with the firm's data key.
def seal(cipher: TenantCipher, user_id: str, secret: str) -> str:
    """Encrypt a TOTP secret; the user id is bound in, so a sealed secret can't be moved."""
    # The user id is bound in, so a sealed secret cannot be moved to another user.
    return cipher.seal(secret.encode(), aad=f"totp:{user_id}")


# Decrypt it again.
def unseal(cipher: TenantCipher, user_id: str, sealed: str) -> str:
    """Decrypt a TOTP secret sealed by `seal` for the same user."""
    # Fails if tampered with or used for another user.
    return cipher.open_field(sealed, aad=f"totp:{user_id}").decode()


# The otpauth:// link authenticator apps import.
def setup_uri(secret: str, account: str) -> str:
    """otpauth:// link that authenticator apps import (also shown as a typed key)."""
    # Includes the issuer and account name.
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER)


# Is this 6-digit code valid right now?
def verify_code(secret: str, code: str) -> bool:
    """True if `code` is valid now, allowing one 30-second step of clock drift either way."""
    # Allow one 30-second step either side for clock drift.
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)
