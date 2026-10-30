"""Session tokens: short-lived JWTs (HS256) that say who the user is, their firm and role."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt

from aicfo.auth.roles import ROLES, Role
from aicfo.config import get_settings

log = logging.getLogger(__name__)
# Marks our tokens, so tokens from another service are rejected.
ISSUER = "aicfo"  # rejects tokens minted for another service with the same secret


# What the API knows about the caller after checking their token.
@dataclass(frozen=True)
class Session:
    """What the API knows about the caller after verifying their token."""

    # Who.
    user_id: str
    # Which firm.
    tenant_id: str
    # Role at sign-in (re-checked in the database on every request).
    role: Role


# Read the signing key once.
@lru_cache
# The key that signs tokens.
def _secret() -> str:
    """The signing key. Required outside dev/test; in dev a random one is made per process."""
    # Settings.
    s = get_settings()
    # A configured secret survives restarts.
    if s.jwt_secret is not None:
        # Use it.
        return s.jwt_secret.get_secret_value()  # configured secret: tokens survive restarts
    # Development: make a throwaway key.
    if s.env in ("dev", "test"):
        # Say so loudly: sign-ins end when the server restarts.
        log.warning("AICFO_JWT_SECRET not set: using a temporary key (sign-ins end on restart)")
        # Random key.
        return secrets.token_urlsafe(48)  # throwaway key, fine for local development
    # Outside dev/test a real secret is mandatory.
    raise RuntimeError("AICFO_JWT_SECRET must be set outside dev/test")


# Create a signed token for a user.
def issue(user_id: str, tenant_id: str, role: Role) -> str:
    """Create a signed token for this user, valid for `session_hours`."""
    # Current time.
    now = datetime.now(UTC)
    # The token's contents.
    claims = {
        "sub": user_id,  # subject: the user id (never the email)
        "tid": tenant_id,  # the firm the session belongs to
        "role": role,  # role at sign-in; re-checked against the database on each request
        "iss": ISSUER,
        "iat": now,  # issued at
        "exp": now + timedelta(hours=get_settings().session_hours),  # expiry
    }
    # Sign with HS256.
    return jwt.encode(claims, _secret(), algorithm="HS256")


# The session inside a token, or None if it is forged, expired or malformed.
def verify(token: str) -> Session | None:
    """The session inside a valid token, or None if it is forged, expired or malformed."""
    # Check the token.
    try:
        # Verify signature, expiry and issuer; only HS256 is accepted.
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=["HS256"],  # pin the algorithm: blocks "alg: none" and key-confusion tricks
            issuer=ISSUER,
            options={"require": ["sub", "tid", "role", "exp", "iss"]},
        )
    # Anything wrong…
    except jwt.PyJWTError:
        # …means not signed in.
        return None  # any failure means "not signed in"
    # An unknown role is treated as no role.
    if claims["role"] not in ROLES:
        # Reject.
        return None  # a role we don't know is treated as no role
    # The verified caller.
    return Session(claims["sub"], claims["tid"], claims["role"])
