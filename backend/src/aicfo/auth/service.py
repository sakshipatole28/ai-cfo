"""Firm accounts and team access: create a firm, confirm MFA, sign in, invite, change roles.

Every function takes an open database session and raises `AuthError` with a user-facing reason.
The audit log records user ids and actions, never emails or names.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aicfo.auth import mfa, passwords, roles, tokens
from aicfo.auth.roles import Role
from aicfo.config import get_settings
from aicfo.crypto import TenantCipher
from aicfo.db import audit
from aicfo.db.models import Invite, Tenant, User
from aicfo.db.pipeline import sync_book

# Days an unused invite stays valid.
INVITE_DAYS = 3  # an unused invite stops working after 72 hours


# A refused action; `status` is the HTTP status the API answers with.
class AuthError(Exception):
    """A refused auth action; `status` is the HTTP status the API should answer with."""

    # Keep the message and the status code.
    def __init__(self, message: str, status: int = 400) -> None:
        # The message is what the console shows.
        super().__init__(message)
        # e.g. 401 sign in, 403 not allowed, 404 not found, 409 conflict.
        self.status = status


# Shown once, right after an account is created.
@dataclass(frozen=True)
class MfaSetup:
    """Returned when an account is created: the user adds this key to an authenticator app."""

    # The new account's id.
    user_id: str
    # Authenticator key to type into the app.
    secret: str  # base32 key to type into the app (shown once, never again)
    # The same as an otpauth:// link.
    uri: str  # otpauth:// link for apps that accept links or QR codes


# Emails are compared lower-cased and trimmed.
def _norm(email: str) -> str:
    """Emails are compared lower-cased and without surrounding spaces."""
    # Normalised email.
    return email.strip().lower()


# Invites keep only a hash of the code.
def _code_hash(code: str) -> str:
    """Invites store only a hash of the code, so a database leak doesn't leak usable invites."""
    # Upper-case so typing in lower case still works.
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


# Open the firm's encryption key.
def _cipher(session: Session, tenant_id: str) -> TenantCipher:
    """The firm's cipher, opened from its wrapped data key."""
    # The firm row.
    tenant = session.get(Tenant, tenant_id)
    # No such firm, or it has no key.
    if tenant is None or tenant.wrapped_data_key is None:
        # 404.
        raise AuthError("firm not found", 404)
    # Unwrap the stored key.
    return mfa.firm_cipher(tenant.id, tenant.wrapped_data_key)


# Create a user: hashed password, sealed authenticator secret, pending MFA.
def _new_user(
    session: Session, tenant: Tenant, email: str, name: str, password: str, role: Role
) -> MfaSetup:
    """Create a user in `pending_mfa` state with a hashed password and a sealed TOTP secret."""
    # Refuse weak passwords first.
    if reason := passwords.weakness(password):  # refuse weak passwords up front
        # 400.
        raise AuthError(f"password too weak: {reason}")
    # One account per email address.
    if session.scalar(select(User.id).where(User.email == email)):  # one account per email
        # 409.
        raise AuthError("an account with this email already exists", 409)
    # A new authenticator secret for this person.
    secret = mfa.new_secret()  # the authenticator secret for this user
    # The account row; the password is stored only as a hash.
    user = User(
        tenant_id=tenant.id,
        email=email,
        name=name.strip(),
        role=role,
        password_hash=passwords.hash_password(password),
        totp_sealed="",  # filled in below, once the user id exists to bind into the seal
    )
    # Queue it.
    session.add(user)
    # Write now so the user has an id.
    session.flush()  # assigns user.id
    # create_firm always sets one.
    assert tenant.wrapped_data_key is not None  # every firm gets a key in create_firm
    # Encrypt the authenticator secret with the firm's key.
    user.totp_sealed = mfa.seal(_cipher(session, tenant.id), user.id, secret)
    # Return the secret once so it can be shown.
    return MfaSetup(user.id, secret, mfa.setup_uri(secret, email))


# Step 1 of sign-up: create the firm and its first Owner.
def create_firm(
    session: Session,
    *,
    firm_name: str,
    firm_type: str,
    registration: str | None,
    owner_name: str,
    email: str,
    password: str,
) -> MfaSetup:
    """Step 1 of sign-up: the Owner creates the firm and their own account."""
    # A readable, URL-safe name.
    slug_base = "-".join(firm_name.lower().split())[:48] or "firm"  # readable, URL-safe id
    # A random suffix keeps slugs unique.
    slug = f"{slug_base}-{secrets.token_hex(3)}"  # random suffix keeps slugs unique
    # The firm row.
    tenant = Tenant(
        slug=slug, display_name=firm_name.strip(), firm_type=firm_type, registration=registration
    )
    # Queue it.
    session.add(tenant)
    # Write now so the firm has an id.
    session.flush()  # assigns tenant.id, needed to bind the data key to this firm
    # Make the firm's data key; store only its wrapped copy.
    _, tenant.wrapped_data_key = mfa.new_firm_key(tenant.id)  # store only the wrapped key
    # The Owner's account.
    setup = _new_user(session, tenant, _norm(email), owner_name, password, "Owner")
    # Log it (ids only).
    audit.append(session, tenant.id, setup.user_id, "firm.created", "tenant", tenant.id)
    # Give the firm the synthetic book to work with.
    if get_settings().seed_new_firms:  # give the new firm the synthetic book to work with
        # Load clients and snapshots for this firm.
        sync_book(session, tenant=tenant, actor=setup.user_id)
    # Authenticator details for the Owner.
    return setup


# Step 2: the first valid authenticator code activates the account and signs in.
def confirm_mfa(session: Session, email: str, password: str, code: str) -> str:
    """Step 2 of sign-up or joining: prove the authenticator works. Returns a session token."""
    # Check email and password.
    user = _check_password(session, email, password)
    # Only unfinished accounts can be confirmed.
    if user.status != "pending_mfa":
        # 409.
        raise AuthError("this account is already set up; sign in instead", 409)
    # Check the 6-digit code.
    _check_code(session, user, code)
    # The account may now sign in.
    user.status = "active"  # the account can now sign in
    # Log it.
    audit.append(session, user.tenant_id, user.id, "auth.mfa_enrolled", "user", user.id)
    # Sign in.
    return _start_session(session, user)


# Password + authenticator code → session token.
def sign_in(session: Session, email: str, password: str, code: str) -> str:
    """Password + authenticator code → session token."""
    # Check email and password.
    user = _check_password(session, email, password)
    # Authenticator not confirmed yet.
    if user.status == "pending_mfa":
        # 409.
        raise AuthError("finish setting up your authenticator first", 409)
    # Access was removed by an Owner or Admin.
    if user.status == "suspended":
        # 403.
        raise AuthError("this account is suspended; ask your firm's Owner or Admin", 403)
    # Check the 6-digit code.
    _check_code(session, user, code)
    # Issue the token.
    return _start_session(session, user)


# Find the user and verify the password; one message for both failures.
def _check_password(session: Session, email: str, password: str) -> User:
    """The user with this email and password. Same error for both failures, so the response
    doesn't reveal which emails have accounts."""
    # Look up by email.
    user = session.scalars(select(User).where(User.email == _norm(email))).first()
    # Unknown email or wrong password.
    if user is None or not passwords.verify_password(password, user.password_hash):
        # 401, same text either way.
        raise AuthError("email or password is wrong", 401)
    # The user.
    return user


# Verify the authenticator code.
def _check_code(session: Session, user: User, code: str) -> None:
    """Verify the 6-digit authenticator code against the user's sealed secret."""
    # Decrypt the user's secret with the firm's key.
    secret = mfa.unseal(_cipher(session, user.tenant_id), user.id, user.totp_sealed)
    # Wrong or expired code.
    if not mfa.verify_code(secret, code):
        # 401.
        raise AuthError("that code is not valid; check the time on your phone", 401)


# Record the sign-in and issue a token.
def _start_session(session: Session, user: User) -> str:
    """Record the sign-in and issue a token."""
    # Remember when.
    user.last_login_at = datetime.now(UTC)
    # Log it.
    audit.append(session, user.tenant_id, user.id, "auth.signed_in", "user", user.id)
    # A signed token for this user, firm and role.
    return tokens.issue(user.id, user.tenant_id, roles_of(user))


# The user's role as a typed value.
def roles_of(user: User) -> Role:
    """The user's role as the typed literal (the column is a plain string)."""
    # A role we do not know.
    if user.role not in roles.ROLES:
        # 403.
        raise AuthError("account has an unknown role", 403)
    # Valid role.
    return user.role


# The signed-in user, re-read from the database.
def current_user(session: Session, s: tokens.Session) -> User:
    """The signed-in user, re-read from the database so suspensions and role changes apply at
    once, not only when the token expires."""
    # Fresh row.
    user = session.get(User, s.user_id)
    # Deleted, another firm, or not active (suspended).
    if user is None or user.tenant_id != s.tenant_id or user.status != "active":
        # 401.
        raise AuthError("please sign in again", 401)
    # Still valid.
    return user


# An Owner or Admin gives someone access.
def invite(session: Session, actor: User, email: str, role: Role) -> str:
    """An Owner or Admin gives someone access. Returns the one-time code (shown once)."""
    # You can only grant roles your own role may grant.
    if role not in roles.grantable(roles_of(actor)):  # e.g. an Admin trying to create an Owner
        # 403.
        raise AuthError(f"your role cannot grant {role}", 403)
    # Normalise.
    email = _norm(email)
    # They must not already have an account.
    if session.scalar(select(User.id).where(User.email == email)):
        # 409.
        raise AuthError("this person already has an account", 409)
    # 10 random hex characters, easy to read out.
    code = secrets.token_hex(5).upper()  # 10 hex characters, easy to read out
    # Store only the code's hash, the role and the expiry.
    inv = Invite(
        tenant_id=actor.tenant_id,
        email=email,
        role=role,
        code_hash=_code_hash(code),
        created_by=actor.id,
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_DAYS),
    )
    # Queue it.
    session.add(inv)
    # Write now so it has an id.
    session.flush()
    # Log the role granted (no email).
    audit.append(
        session, actor.tenant_id, actor.id, "team.invited", "invite", inv.id, {"role": role}
    )
    # Shown once to the inviter.
    return code


# The employee joins with their code.
def accept_invite(session: Session, code: str, name: str, password: str) -> MfaSetup:
    """The employee joins with their code; they then confirm MFA like a new Owner does."""
    # Find the invite by the code's hash.
    inv = session.scalars(select(Invite).where(Invite.code_hash == _code_hash(code))).first()
    # Current time.
    now = datetime.now(UTC)
    # SQLite returns naive times; treat them as UTC.
    expires = inv.expires_at.replace(tzinfo=UTC) if inv and not inv.expires_at.tzinfo else None
    # Unknown, revoked or already used.
    if inv is None or inv.revoked or inv.accepted_at is not None:
        # 404.
        raise AuthError("this invite code is not valid", 404)
    # Past its expiry.
    if (expires or inv.expires_at) < now:
        # 410.
        raise AuthError("this invite has expired; ask for a new one", 410)
    # The firm that invited them.
    tenant = session.get(Tenant, inv.tenant_id)
    # Invites are deleted with their firm.
    assert tenant is not None  # invites cascade-delete with their firm
    # Create the account with the invited email and role.
    setup = _new_user(session, tenant, inv.email, name, password, inv.role)  # type: ignore[arg-type]
    # The code cannot be used again.
    inv.accepted_at = now  # the code can't be used twice
    # Log it.
    audit.append(session, tenant.id, setup.user_id, "team.joined", "invite", inv.id)
    # Authenticator details for the new member.
    return setup


# How many active Owners the firm has.
def _active_owners(session: Session, tenant_id: str) -> int:
    """How many active Owners the firm has (used to keep at least one)."""
    # Count active Owners of this firm.
    count = session.scalar(
        select(func.count(User.id)).where(
            User.tenant_id == tenant_id, User.role == "Owner", User.status == "active"
        )
    )
    # Zero if none.
    return int(count or 0)


# A member of the actor's own firm.
def _target(session: Session, actor: User, user_id: str) -> User:
    """A member of the actor's own firm (other firms' users look like they don't exist)."""
    # Look them up.
    target = session.get(User, user_id)
    # Other firms' members look like they do not exist.
    if target is None or target.tenant_id != actor.tenant_id:
        # 404.
        raise AuthError("member not found", 404)
    # The member.
    return target


# Give a member a different role, if the rules allow.
def change_role(session: Session, actor: User, user_id: str, new_role: Role) -> User:
    """Give a member a different role, if the rules in `roles.check_change` allow it."""
    # Find the member.
    target = _target(session, actor, user_id)
    # Ask the rules whether this is allowed.
    reason = roles.check_change(
        actor_id=actor.id,
        actor_role=roles_of(actor),
        target_id=target.id,
        target_role=roles_of(target),
        new_role=new_role,
        active_owners=_active_owners(session, actor.tenant_id),
    )
    # Not allowed…
    if reason:
        # …say why.
        raise AuthError(reason, 403)
    # Change the role, remembering the old one.
    old, target.role = target.role, new_role
    # Log from → to (roles only).
    audit.append(
        session,
        actor.tenant_id,
        actor.id,
        "team.role_changed",
        "user",
        target.id,
        {"from": old, "to": new_role},
    )
    # The updated member.
    return target


# Suspend (removes access at once) or restore a member.
def set_suspended(session: Session, actor: User, user_id: str, suspended: bool) -> User:
    """Suspend (removes access at once) or restore a member."""
    # Find the member.
    target = _target(session, actor, user_id)
    # Same rules as a role change; suspending an Owner is a demotion.
    reason = roles.check_change(
        actor_id=actor.id,
        actor_role=roles_of(actor),
        target_id=target.id,
        target_role=roles_of(target),
        new_role=None if suspended else roles_of(target),  # restoring keeps the same role
        active_owners=_active_owners(session, actor.tenant_id),
    )
    # Not allowed…
    if reason:
        # …say why.
        raise AuthError(reason, 403)
    # Restoring someone who is not suspended.
    if not suspended and target.status != "suspended":
        # 409.
        raise AuthError("this member is not suspended", 409)
    # Apply it.
    target.status = "suspended" if suspended else "active"
    # Audit action name.
    action = "team.suspended" if suspended else "team.restored"
    # Log it.
    audit.append(session, actor.tenant_id, actor.id, action, "user", target.id)
    # The updated member.
    return target
