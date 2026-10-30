"""FastAPI dependencies: who is calling, and are they allowed to do this?

Two kinds of caller:
  * a signed-in firm member: `Authorization: Bearer <session token>` from /v1/auth/*;
  * automation (n8n): `Authorization: Bearer <AICFO_AUTOMATION_TOKEN>`.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from aicfo.auth import roles, service, tokens
from aicfo.config import get_settings
from aicfo.db.models import User
from aicfo.db.session import get_session


# Who is calling: a person or the automation service.
@dataclass(frozen=True)
class Caller:
    """Either a firm member (`user` set) or the automation service (`user` is None)."""

    # Set for a person; None for automation (n8n).
    user: User | None

    @property
    # The id written to the audit log.
    def actor(self) -> str:
        """The id written to the audit log."""
        # A person's id, or "automation".
        return self.user.id if self.user else "automation"


# Extract the token from an "Authorization: Bearer …" header.
def _bearer(authorization: str | None) -> str | None:
    """The token from an `Authorization: Bearer …` header, if present."""
    # Header present and correctly formed.
    if authorization and authorization.startswith("Bearer "):
        # The token.
        return authorization.removeprefix("Bearer ").strip()
    # No usable token.
    return None


# Is this the automation token?
def _is_automation(token: str | None) -> bool:
    """True if the token is the automation token. Unset token: only allowed in dev/test."""
    # Settings.
    s = get_settings()
    # No token configured…
    if s.automation_token is None:
        # …only dev/test allow tokenless local automation.
        return s.env in ("dev", "test") and token is None  # local n8n with no token configured
    # Compare in constant time.
    return token is not None and secrets.compare_digest(
        token, s.automation_token.get_secret_value()
    )  # constant-time compare


# The person behind a session token, or None.
def _user(session: Session, token: str | None) -> User | None:
    """The signed-in member for a session token, or None if the token isn't a valid session."""
    # Nothing to check.
    if token is None:
        # Not signed in.
        return None
    # Check signature, expiry and issuer.
    s = tokens.verify(token)  # checks signature, expiry and issuer
    # Invalid token.
    if s is None:
        # Not signed in.
        return None
    # Re-read the user from the database.
    try:
        # Suspensions and role changes apply immediately.
        return service.current_user(session, s)  # re-checks status and role in the database
    # Suspended, deleted or other firm.
    except service.AuthError:
        # Not signed in.
        return None


# Dependency: require a signed-in person.
def signed_in(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Require a signed-in firm member."""
    # Look them up.
    user = _user(session, _bearer(authorization))
    # Not signed in…
    if user is None:
        # …401 Unauthorized.
        raise HTTPException(401, "please sign in")
    # The person.
    return user


# Dependency factory: require a signed-in person whose role has a capability.
def needs(capability: roles.Capability) -> Callable[[User], User]:
    """Require a signed-in member whose role has `capability`."""

    # The actual dependency.
    def check(user: Annotated[User, Depends(signed_in)]) -> User:
        # Role lacks the capability…
        if not roles.can(service.roles_of(user), capability):
            # …403 Forbidden.
            raise HTTPException(403, f"your role ({user.role}) cannot do this")
        # Allowed.
        return user

    # The dependency.
    return check


# Dependency factory: automation token OR a person with the capability.
def automation_or(capability: roles.Capability) -> Callable[..., Caller]:
    """Allow the automation token, or a signed-in member with `capability`."""

    # The actual dependency.
    def check(
        session: Annotated[Session, Depends(get_session)],
        authorization: Annotated[str | None, Header()] = None,
    ) -> Caller:
        # Whatever token was sent.
        token = _bearer(authorization)
        # n8n.
        if _is_automation(token):  # n8n
            # Automation caller.
            return Caller(None)
        # Otherwise a person.
        user = _user(session, token)  # or a person
        # Neither.
        if user is None:
            # Production without an automation token: say automation is off.
            if get_settings().automation_token is None and get_settings().env not in (
                "dev",
                "test",
            ):
                # Service unavailable.
                raise HTTPException(503, "automation is disabled: set AICFO_AUTOMATION_TOKEN")
            # Ask them to sign in or use the token.
            raise HTTPException(401, "sign in, or send the automation token")
        # A person without the capability.
        if not roles.can(service.roles_of(user), capability):
            # Forbidden.
            raise HTTPException(403, f"your role ({user.role}) cannot do this")
        # Allowed.
        return Caller(user)

    # The dependency.
    return check
