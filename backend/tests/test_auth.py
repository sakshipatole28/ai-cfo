"""Firm accounts and team access: the Owner creates the firm, Owners/Admins grant roles."""

from collections.abc import Iterator

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from aicfo.auth import passwords, roles, tokens
from aicfo.db import migrate
from aicfo.db.session import get_engine
from aicfo.main import create_app

PASSWORD = "correct horse battery"


@pytest.fixture
def client() -> Iterator[TestClient]:
    eng: Engine = get_engine()
    migrate.upgrade(eng)
    yield TestClient(create_app())
    migrate.downgrade(eng)


def finish_mfa(client: TestClient, email: str, setup: dict[str, str]) -> dict[str, str]:
    """Confirm the authenticator with a real code and return auth headers."""
    code = pyotp.TOTP(setup["totp_secret"]).now()
    r = client.post(
        "/v1/auth/mfa/confirm", json={"email": email, "password": PASSWORD, "code": code}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def new_firm(
    client: TestClient, email: str = "owner@a.example", name: str = "A Wealth"
) -> dict[str, str]:
    r = client.post(
        "/v1/auth/firms",
        json={
            "firm_name": name,
            "firm_type": "RIA",
            "owner_name": "Owner A",
            "email": email,
            "password": PASSWORD,
        },
    )
    assert r.status_code == 201, r.text
    return finish_mfa(client, email, r.json())


def join(client: TestClient, inviter: dict[str, str], email: str, role: str) -> dict[str, str]:
    """Inviter grants `role`; the employee joins with the code and sets up MFA."""
    r = client.post("/v1/team/invites", json={"email": email, "role": role}, headers=inviter)
    assert r.status_code == 201, r.text
    setup = client.post(
        "/v1/auth/invites/accept",
        json={"code": r.json()["code"], "name": "Employee", "password": PASSWORD},
    )
    assert setup.status_code == 201, setup.text
    return finish_mfa(client, email, setup.json())


def member_id(client: TestClient, headers: dict[str, str]) -> str:
    return str(client.get("/v1/me", headers=headers).json()["id"])


# ---------------- pure rules ----------------
def test_role_rules() -> None:
    assert roles.grantable("Owner") == roles.ROLES
    assert roles.grantable("Admin") == ("Adviser", "Analyst", "Compliance")
    assert roles.grantable("Adviser") == ()
    base = {"actor_id": "a", "target_id": "b", "active_owners": 2}
    assert (
        roles.check_change(actor_role="Owner", target_role="Adviser", new_role="Admin", **base)
        is None
    )
    assert "Owner" in str(
        roles.check_change(actor_role="Admin", target_role="Admin", new_role="Adviser", **base)
    )
    assert "cannot grant" in str(
        roles.check_change(actor_role="Admin", target_role="Analyst", new_role="Owner", **base)
    )
    assert "own" in str(
        roles.check_change(
            **{**base, "target_id": "a"},
            actor_role="Owner",
            target_role="Owner",
            new_role="Adviser",
        )
    )
    last = {**base, "active_owners": 1}
    assert "at least one" in str(
        roles.check_change(actor_role="Owner", target_role="Owner", new_role="Adviser", **last)
    )


def test_passwords_are_hashed_and_checked() -> None:
    stored = passwords.hash_password(PASSWORD)
    assert PASSWORD not in stored and passwords.verify_password(PASSWORD, stored)
    assert not passwords.verify_password("wrong password!!", stored)
    assert not passwords.verify_password(PASSWORD, "garbage")
    assert passwords.weakness("short") and passwords.weakness("a" * 20)


def test_tokens_reject_tampering() -> None:
    t = tokens.issue("u1", "t1", "Adviser")
    assert tokens.verify(t) == tokens.Session("u1", "t1", "Adviser")
    head, body, sig = t.split(".")
    assert tokens.verify(f"{head}.{body}.{sig[:-2]}xx") is None


# ---------------- flows over HTTP ----------------
def test_owner_creates_firm_and_sees_full_capabilities(client: TestClient) -> None:
    owner = new_firm(client)
    me = client.get("/v1/me", headers=owner).json()
    assert me["role"] == "Owner" and me["firm"]["name"] == "A Wealth"
    assert "manageAdmins" in me["capabilities"] and me["can_grant"] == list(roles.ROLES)


def test_signup_needs_a_valid_authenticator_code(client: TestClient) -> None:
    r = client.post(
        "/v1/auth/firms",
        json={
            "firm_name": "B Wealth",
            "firm_type": "MFD",
            "owner_name": "Owner B",
            "email": "b@b.example",
            "password": PASSWORD,
        },
    )
    bad = client.post(
        "/v1/auth/mfa/confirm",
        json={"email": "b@b.example", "password": PASSWORD, "code": "000000"},
    )
    assert r.status_code == 201 and bad.status_code == 401
    # Not usable until MFA is confirmed.
    code = pyotp.TOTP(r.json()["totp_secret"]).now()
    early = client.post(
        "/v1/auth/sign-in", json={"email": "b@b.example", "password": PASSWORD, "code": code}
    )
    assert early.status_code == 409


def test_sign_in_and_wrong_password(client: TestClient) -> None:
    r = client.post(
        "/v1/auth/firms",
        json={
            "firm_name": "C Wealth",
            "firm_type": "RIA",
            "owner_name": "Owner C",
            "email": "c@c.example",
            "password": PASSWORD,
        },
    )
    finish_mfa(client, "c@c.example", r.json())
    totp = pyotp.TOTP(r.json()["totp_secret"])
    ok = client.post(
        "/v1/auth/sign-in", json={"email": "C@c.example ", "password": PASSWORD, "code": totp.now()}
    )
    assert ok.status_code == 200 and ok.json()["token"]
    wrong = client.post(
        "/v1/auth/sign-in",
        json={"email": "c@c.example", "password": "not the password", "code": totp.now()},
    )
    unknown = client.post(
        "/v1/auth/sign-in", json={"email": "x@c.example", "password": PASSWORD, "code": totp.now()}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # doesn't reveal which emails have accounts


def test_owner_grants_admin_and_admin_grants_staff(client: TestClient) -> None:
    owner = new_firm(client)
    admin = join(client, owner, "admin@a.example", "Admin")
    adviser = join(client, admin, "adviser@a.example", "Adviser")
    assert client.get("/v1/me", headers=adviser).json()["role"] == "Adviser"
    # Admin cannot create Owners or Admins.
    r = client.post(
        "/v1/team/invites", json={"email": "x@a.example", "role": "Owner"}, headers=admin
    )
    assert r.status_code == 403
    # Advisers cannot manage the team at all.
    assert client.get("/v1/team", headers=adviser).status_code == 403
    team = client.get("/v1/team", headers=admin).json()
    assert sorted(m["role"] for m in team["members"]) == ["Admin", "Adviser", "Owner"]


def test_invite_codes_work_once(client: TestClient) -> None:
    owner = new_firm(client)
    code = client.post(
        "/v1/team/invites", json={"email": "e@a.example", "role": "Analyst"}, headers=owner
    ).json()["code"]
    body = {"code": code, "name": "Employee E", "password": PASSWORD}
    assert client.post("/v1/auth/invites/accept", json=body).status_code == 201
    assert client.post("/v1/auth/invites/accept", json=body).status_code == 404


def test_role_changes_follow_the_rules(client: TestClient) -> None:
    owner = new_firm(client)
    admin = join(client, owner, "admin@a.example", "Admin")
    analyst = join(client, admin, "analyst@a.example", "Analyst")
    owner_id, admin_id, analyst_id = (member_id(client, h) for h in (owner, admin, analyst))
    # Admin promotes the analyst to adviser: allowed.
    r = client.patch(f"/v1/team/{analyst_id}", json={"role": "Adviser"}, headers=admin)
    assert r.status_code == 200 and r.json()["role"] == "Adviser"
    # Admin cannot touch the Owner; nobody can change themselves; the last Owner stays.
    assert (
        client.patch(f"/v1/team/{owner_id}", json={"role": "Adviser"}, headers=admin).status_code
        == 403
    )
    assert (
        client.patch(f"/v1/team/{admin_id}", json={"role": "Owner"}, headers=admin).status_code
        == 403
    )
    assert (
        client.patch(f"/v1/team/{owner_id}", json={"role": "Adviser"}, headers=owner).status_code
        == 403
    )


def test_suspension_ends_access_immediately(client: TestClient) -> None:
    owner = new_firm(client)
    adviser = join(client, owner, "adv@a.example", "Adviser")
    adviser_id = member_id(client, adviser)
    r = client.patch(f"/v1/team/{adviser_id}", json={"status": "suspended"}, headers=owner)
    assert r.status_code == 200
    assert client.get("/v1/me", headers=adviser).status_code == 401  # old token no longer works
    assert (
        client.patch(f"/v1/team/{adviser_id}", json={"status": "active"}, headers=owner).status_code
        == 200
    )
    assert client.get("/v1/me", headers=adviser).status_code == 200


def test_firms_cannot_see_each_other(client: TestClient) -> None:
    a = new_firm(client, "owner@a.example", "A Wealth")
    b = new_firm(client, "owner@b.example", "B Wealth")
    b_id = member_id(client, b)
    assert client.patch(f"/v1/team/{b_id}", json={"role": "Adviser"}, headers=a).status_code == 404
    names = {m["email"] for m in client.get("/v1/team", headers=a).json()["members"]}
    assert names == {"owner@a.example"}
