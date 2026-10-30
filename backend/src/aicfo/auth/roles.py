"""Roles, capabilities and who may grant what. Pure functions: no database, no HTTP.

How access works in a firm:
  1. The Owner creates the firm account (`/v1/auth/firms`) and becomes its first Owner.
  2. Owners and Admins give employees access by inviting them with a role.
  3. The employee joins with the one-time invite code; nobody can self-register into a firm.

The console has the same rules in `frontend/src/lib/roles.ts`; keep the two in step.
"""

from __future__ import annotations

from typing import Literal

# Every role a firm member can hold, from most to least authority.
# Every role a firm member can hold, from most to least authority.
Role = Literal["Owner", "Admin", "Adviser", "Analyst", "Compliance"]
# The same roles as a tuple, for looping and validation.
ROLES: tuple[Role, ...] = ("Owner", "Admin", "Adviser", "Analyst", "Compliance")

# A capability is one thing a role is allowed to do.
# A capability is one thing a role is allowed to do.
Capability = Literal[
    "approve",  # accept findings and approve client reviews (registered advisers only)
    "seeAll",  # see every client in the firm, not only assigned ones
    "manageTeam",  # invite people, change roles, suspend (rules below limit whom)
    "manageAdmins",  # grant or remove the Owner and Admin roles
    "requestAccess",  # ask a client for consent to see their data
    "settings",  # firm settings, including the AI kill switch
    "audit",  # read and verify the audit log
    "ingest",  # upload statements, connect brokers
]

# Which capabilities each role has. Admin runs the office (people and audit) but cannot
# approve advice or read every client's portfolio.
# Which capabilities each role has.
CAPABILITIES: dict[Role, frozenset[Capability]] = {
    "Owner": frozenset(
        {
            "approve",
            "seeAll",
            "manageTeam",
            "manageAdmins",
            "requestAccess",
            "settings",
            "audit",
            "ingest",
        }
    ),
    "Admin": frozenset({"manageTeam", "audit"}),
    "Adviser": frozenset({"approve", "requestAccess", "ingest"}),
    "Analyst": frozenset({"seeAll", "ingest"}),
    "Compliance": frozenset({"seeAll", "audit"}),
}

# Roles only an Owner may hand out or take away.
# Roles only an Owner may hand out or take away.
PRIVILEGED: frozenset[Role] = frozenset({"Owner", "Admin"})


# True if `role` includes `capability`.
def can(role: Role, capability: Capability) -> bool:
    """True if `role` includes `capability`."""
    # Look it up in the role's set.
    return capability in CAPABILITIES[role]


# The roles `actor` may give to someone when inviting or changing a role.
def grantable(actor: Role) -> tuple[Role, ...]:
    """The roles `actor` may give to someone when inviting or changing a role."""
    if can(actor, "manageAdmins"):  # Owners can grant every role, including Owner
        return ROLES
    if can(actor, "manageTeam"):  # Admins can grant only the non-privileged roles
        return tuple(r for r in ROLES if r not in PRIVILEGED)
    return ()  # everyone else cannot grant anything


# Why `actor` may not change `target`; None means allowed. Every team change goes through here.
def check_change(
    *,
    actor_id: str,
    actor_role: Role,
    target_id: str,
    target_role: Role,
    new_role: Role | None,
    active_owners: int,
) -> str | None:
    """Why `actor` may not change `target` (to `new_role`, or suspend when None); None if allowed.

    Rules: you cannot change yourself; only Owners touch Owners and Admins; you can only grant
    roles you are allowed to grant; the firm must keep at least one active Owner.
    """
    if actor_id == target_id:  # self-service promotion or suspension is never allowed
        return "you cannot change your own role or access"
    if not can(actor_role, "manageTeam"):  # Advisers, Analysts and Compliance cannot manage people
        return "your role cannot manage the team"
    if target_role in PRIVILEGED and not can(
        actor_role, "manageAdmins"
    ):  # Admins can't touch peers
        return "only an Owner can change an Owner or an Admin"
    if new_role is not None and new_role not in grantable(actor_role):  # e.g. Admin → Owner
        return f"your role cannot grant {new_role}"
    leaving_owner = target_role == "Owner" and new_role != "Owner"  # demotion or suspension
    if leaving_owner and active_owners <= 1:  # someone must always be able to run the firm
        return "the firm must keep at least one active Owner"
    return None  # every rule passed
