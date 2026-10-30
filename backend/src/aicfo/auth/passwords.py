"""Password hashing with scrypt (Python standard library), so no plain password is ever stored.

Stored format: `scrypt$<n>$<r>$<p>$<salt-hex>$<hash-hex>`. The parameters travel with the hash,
so they can be raised later without breaking existing accounts.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# scrypt cost parameters: N (CPU/memory cost), r (block size), p (parallelism).
# N=2**14, r=8 uses about 16 MB per hash, the usual interactive-login setting.
# scrypt cost settings (memory/CPU cost, block size, parallelism).
N, R, P = 2**14, 8, 1
# Minimum password length.
MIN_LENGTH = 12  # long passphrases beat complexity rules


# Hash a password with a fresh random salt.
def hash_password(password: str) -> str:
    """Hash `password` with a fresh random salt and return the storable string."""
    # Random salt, so equal passwords get different hashes.
    salt = secrets.token_bytes(16)  # a new salt per password defeats precomputed tables
    # The slow, memory-hard hash.
    digest = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=32)
    # Store the settings, salt and hash together.
    return f"scrypt${N}${R}${P}${salt.hex()}${digest.hex()}"  # parameters + salt + hash


# Check a password against a stored hash.
def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches the stored hash. Never raises on a malformed record."""
    # Unpack the stored string.
    try:
        # Settings, salt and hash.
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")  # unpack the stored format
    # Malformed record.
    except ValueError:
        # Not a hash we recognise.
        return False  # not a hash we recognise
    # Only scrypt is supported.
    if scheme != "scrypt":
        # Refuse rather than guess.
        return False  # unknown scheme: refuse rather than guess
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32
    )
    # Constant-time comparison, so timing reveals nothing.
    return hmac.compare_digest(digest.hex(), hash_hex)  # constant-time compare: no timing leak


# A reason the password is too weak, or None.
def weakness(password: str) -> str | None:
    """A reason the password is too weak, or None if acceptable."""
    # Too short.
    if len(password) < MIN_LENGTH:
        # Say how long.
        return f"use at least {MIN_LENGTH} characters"
    # Too repetitive.
    if len(set(password)) < 5:  # rejects things like "aaaaaaaaaaaa"
        # Say why.
        return "use a less repetitive password"
    # Acceptable.
    return None
