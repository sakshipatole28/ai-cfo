"""Firm accounts and team access over HTTP.

POST /v1/auth/firms            Owner creates the firm            → authenticator key
POST /v1/auth/invites/accept   employee joins with an invite code → authenticator key
POST /v1/auth/mfa/confirm      first code from the app            → session token
POST /v1/auth/sign-in          email + password + code            → session token
GET  /v1/me                    who am I, my firm, what I can do
GET  /v1/team                  members and open invites            [manageTeam]
POST /v1/team/invites          give someone access with a role     [manageTeam]
PATCH /v1/team/{user_id}       change role / suspend / restore     [manageTeam]
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aicfo.auth import roles, service
from aicfo.auth.deps import needs, signed_in
from aicfo.auth.roles import Role
from aicfo.db.models import Invite, Tenant, User
from aicfo.db.session import get_session

# All routes live under /v1.
router = APIRouter(prefix="/v1", tags=["auth"])
# A database session; one transaction per request.
DB = Annotated[Session, Depends(get_session)]  # one transaction per request
# A 6-digit authenticator code.
Code = Annotated[str, Field(pattern=r"^\d{6}$")]  # a 6-digit authenticator code
# At least 12 characters.
Password = Annotated[str, Field(min_length=12, max_length=200)]


# Body of "create a firm".
class FirmIn(BaseModel):
    # Display name.
    firm_name: str = Field(min_length=2, max_length=120)
    # RIA (adviser) or MFD (distributor).
    firm_type: Literal["RIA", "MFD"]  # SEBI-registered adviser or mutual fund distributor
    # SEBI RIA or AMFI ARN number.
    registration: str | None = Field(None, max_length=32)  # e.g. INA000012345 or ARN-123456
    # The Owner's name.
    owner_name: str = Field(min_length=2, max_length=120)
    # Login name.
    email: EmailStr
    # Checked for strength; stored only as a hash.
    password: Password


# Body of "join with an invite code".
class AcceptIn(BaseModel):
    # The one-time invite code.
    code: str = Field(min_length=6, max_length=20)
    # The employee's name.
    name: str = Field(min_length=2, max_length=120)
    # Their chosen password.
    password: Password


# Body of sign-in and of the first authenticator confirmation.
class ConfirmIn(BaseModel):
    # Login name.
    email: EmailStr
    # Password.
    password: str
    # Authenticator code.
    code: Code


# Body of "invite someone".
class InviteIn(BaseModel):
    # Who to invite.
    email: EmailStr
    # The role to give them.
    role: Role


# Body of "change a member": send a role OR a status.
class MemberPatch(BaseModel):
    # New role…
    role: Role | None = None  # new role, or
    # …or suspend / restore.
    status: Literal["active", "suspended"] | None = None  # suspend / restore


# Turn a refusal from the service into an HTTP error.
def _refuse(exc: service.AuthError) -> HTTPException:
    """Turn a service refusal into the HTTP error the console shows."""
    # Same status and message.
    return HTTPException(exc.status, str(exc))


# The authenticator details shown once after creating an account.
def _setup(s: service.MfaSetup) -> dict[str, str]:
    """The authenticator details shown once after creating an account."""
    # User id, key and otpauth link.
    return {"user_id": s.user_id, "totp_secret": s.secret, "totp_uri": s.uri}


# A member as the Team page shows them.
def _member(u: User) -> dict[str, Any]:
    """A member as the console's Team page shows them."""
    # No password hash, no secrets.
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "status": u.status,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
    }


# POST /v1/auth/firms: create a firm and its Owner.
@router.post("/auth/firms", status_code=201)
# Step 1 of 2.
def create_firm(body: FirmIn, session: DB) -> dict[str, str]:
    # Run the service.
    try:
        # Return the authenticator key.
        return _setup(
            service.create_firm(
                session,
                firm_name=body.firm_name,
                firm_type=body.firm_type,
                registration=body.registration,
                owner_name=body.owner_name,
                email=str(body.email),
                password=body.password,
            )
        )
    # A refusal.
    except service.AuthError as exc:
        # As an HTTP error.
        raise _refuse(exc) from exc


# POST /v1/auth/invites/accept: join with an invite code.
@router.post("/auth/invites/accept", status_code=201)
# Step 1 of 2 for an employee.
def accept_invite(body: AcceptIn, session: DB) -> dict[str, str]:
    # Run the service.
    try:
        # Return the authenticator key.
        return _setup(service.accept_invite(session, body.code, body.name, body.password))
    # A refusal.
    except service.AuthError as exc:
        # As an HTTP error.
        raise _refuse(exc) from exc


# POST /v1/auth/mfa/confirm: first code from the app → session token.
@router.post("/auth/mfa/confirm")
# Step 2 of 2.
def confirm_mfa(body: ConfirmIn, session: DB) -> dict[str, str]:
    # Run the service.
    try:
        # The session token.
        return {"token": service.confirm_mfa(session, str(body.email), body.password, body.code)}
    # A refusal.
    except service.AuthError as exc:
        # As an HTTP error.
        raise _refuse(exc) from exc


# POST /v1/auth/sign-in: email + password + code → session token.
@router.post("/auth/sign-in")
# Normal sign-in.
def sign_in(body: ConfirmIn, session: DB) -> dict[str, str]:
    # Run the service.
    try:
        # The session token.
        return {"token": service.sign_in(session, str(body.email), body.password, body.code)}
    # A refusal.
    except service.AuthError as exc:
        # As an HTTP error.
        raise _refuse(exc) from exc


# GET /v1/me: who am I, my firm and what I can do.
@router.get("/me")
# Needs a signed-in user.
def me(user: Annotated[User, Depends(signed_in)], session: DB) -> dict[str, Any]:
    # Their firm.
    firm = session.get(Tenant, user.tenant_id)
    # Users are deleted with their firm.
    assert firm is not None  # users cascade-delete with their firm
    # Their role.
    role = service.roles_of(user)
    # Member, firm, capabilities (so the console hides what you cannot do) and the roles you may grant.
    return {
        **_member(user),
        "firm": {
            "id": firm.id,
            "name": firm.display_name,
            "type": firm.firm_type,
            "registration": firm.registration,
            "slug": firm.slug,
        },
        "capabilities": sorted(roles.CAPABILITIES[role]),  # the console hides what you can't do
        "can_grant": list(roles.grantable(role)),  # roles offered in the invite form
    }


# GET /v1/team: members and open invites (Owners and Admins).
@router.get("/team")
# Needs the manageTeam capability.
def team(user: Annotated[User, Depends(needs("manageTeam"))], session: DB) -> dict[str, Any]:
    # Everyone in this firm.
    members = session.scalars(select(User).where(User.tenant_id == user.tenant_id)).all()
    # Current time.
    now = datetime.now(UTC)
    # Invites still unused, unrevoked and unexpired.
    invites = [
        {"id": i.id, "email": i.email, "role": i.role, "expires_at": i.expires_at.isoformat()}
        for i in session.scalars(select(Invite).where(Invite.tenant_id == user.tenant_id)).all()
        if i.accepted_at is None
        and not i.revoked
        and (i.expires_at if i.expires_at.tzinfo else i.expires_at.replace(tzinfo=UTC)) > now
    ]
    # Members and open invites.
    return {"members": [_member(m) for m in members], "invites": invites}


# POST /v1/team/invites: give someone access with a role.
@router.post("/team/invites", status_code=201)
# Needs manageTeam; the role must be one the caller may grant.
def invite(
    body: InviteIn, user: Annotated[User, Depends(needs("manageTeam"))], session: DB
) -> dict[str, str]:
    # Run the service.
    try:
        # Create the invite.
        code = service.invite(session, user, str(body.email), body.role)
    # A refusal.
    except service.AuthError as exc:
        # As an HTTP error.
        raise _refuse(exc) from exc
    # The code is returned once so the Owner/Admin can pass it on; only its hash is stored.
    # Only its hash is stored; this is the only time it is shown.
    return {"code": code, "email": str(body.email), "role": body.role}


# PATCH /v1/team/{id}: change a member's role, or suspend / restore.
@router.patch("/team/{user_id}")
# Needs manageTeam; the rules in roles.py decide what is allowed.
def update_member(
    user_id: str,
    body: MemberPatch,
    user: Annotated[User, Depends(needs("manageTeam"))],
    session: DB,
) -> dict[str, Any]:
    # Exactly one of role or status.
    if (body.role is None) == (body.status is None):
        # Bad request.
        raise HTTPException(422, "send either a role or a status")
    # Run the service.
    try:
        # Role change…
        if body.role is not None:
            # …apply it.
            target = service.change_role(session, user, user_id, body.role)
        # …or suspend / restore.
        else:
            # Apply it.
            target = service.set_suspended(session, user, user_id, body.status == "suspended")
    # A refusal.
    except service.AuthError as exc:
        # As an HTTP error.
        raise _refuse(exc) from exc
    # The updated member.
    return _member(target)
