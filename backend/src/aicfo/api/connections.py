"""Live broker connection endpoints (Dhan). Read-only; tokens are used once and discarded."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Response
from fastapi.responses import RedirectResponse

from aicfo.config import REPO_ROOT, get_settings
from aicfo.core.book import load_book
from aicfo.sources.dhan import DhanClient, DhanError, TokenExpiredError, reconcile

router = APIRouter(prefix="/v1/connections/dhan", tags=["connections"])
FIXTURE = REPO_ROOT / "data" / "synthetic" / "dhan_holdings_sandbox.json"
STATEMENT = REPO_ROOT / "data" / "synthetic" / "cdsl_statement.json"
_PENDING: dict[str, tuple[str, float]] = {}  # one-time nonce -> (client_id, created)
FLOW_TTL = 600


def _sandbox_transport() -> httpx.MockTransport:
    holdings = json.loads(FIXTURE.read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/generate-consent"):
            return httpx.Response(
                200,
                json={
                    "consentAppId": f"sandbox-{secrets.token_hex(4)}",
                    "consentAppStatus": "GENERATED",
                    "status": "success",
                },
            )
        if path.endswith("/consumeApp-consent"):
            return httpx.Response(
                200,
                json={
                    "dhanClientId": "1000000001",
                    "dhanClientName": "SANDBOX USER",
                    "dhanClientUcc": "X0000",
                    "givenPowerOfAttorney": False,
                    "accessToken": "sandbox." + secrets.token_hex(8),
                    "expiryTime": "2026-10-20T09:00:00",
                },
            )
        if path.endswith("/holdings"):
            return httpx.Response(200, json=holdings)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _client() -> DhanClient:
    s = get_settings()
    if s.dhan_mode == "off":
        raise HTTPException(503, "Live broker connection is switched off")
    if s.dhan_mode == "sandbox":
        return DhanClient(
            "sandbox", "sandbox", "1000000001", httpx.Client(transport=_sandbox_transport())
        )
    if not (s.dhan_app_id and s.dhan_app_secret and s.dhan_client_id):
        raise HTTPException(503, "Dhan API key, secret and client id are not configured")
    return DhanClient(s.dhan_app_id, s.dhan_app_secret.get_secret_value(), s.dhan_client_id)


@router.post("/start")
def start(client_id: str, response: Response) -> dict[str, str]:
    if client_id not in load_book().clients:
        raise HTTPException(404, "client not found")
    dhan = _client()
    try:
        consent = dhan.generate_consent()
    except DhanError as exc:
        raise HTTPException(502, str(exc)) from exc
    nonce = secrets.token_urlsafe(24)
    _PENDING[nonce] = (client_id, time.time())
    response.set_cookie(
        "dhan_flow",
        nonce,
        max_age=FLOW_TTL,
        httponly=True,
        samesite="lax",
        secure=get_settings().env == "prod",
    )
    mode = get_settings().dhan_mode
    login = (
        f"/v1/connections/dhan/sandbox-login?consentAppId={consent}"
        if mode == "sandbox"
        else DhanClient.login_url(consent)
    )
    return {"login_url": login, "mode": mode}


@router.get("/sandbox-login", include_in_schema=False)
def sandbox_login(consentAppId: str) -> RedirectResponse:  # noqa: N803 - Dhan's parameter name
    if get_settings().dhan_mode != "sandbox":
        raise HTTPException(404)
    return RedirectResponse(
        f"/v1/connections/dhan/callback?tokenId=sandbox-{consentAppId}", status_code=302
    )


@router.get("/callback")
def callback(tokenId: str, dhan_flow: str | None = Cookie(default=None)) -> dict[str, Any]:  # noqa: N803
    pending = _PENDING.pop(dhan_flow, None) if dhan_flow else None
    if pending is None or time.time() - pending[1] > FLOW_TTL:
        raise HTTPException(
            400, "This sign-in link is invalid or expired. Start the connection again."
        )
    client_id = pending[0]
    dhan = _client()
    try:
        access = dhan.consume_consent(tokenId)
        holdings = dhan.fetch_holdings(access)
    except TokenExpiredError as exc:
        raise HTTPException(401, str(exc)) from exc
    except DhanError as exc:
        raise HTTPException(502, str(exc)) from exc
    statement = {
        k: float(v) for k, v in json.loads(STATEMENT.read_text()).get(client_id, {}).items()
    }
    differences = reconcile(holdings, statement)
    expires = access.expires_at
    del access  # session mode: the token is not stored anywhere
    return {
        "client_id": client_id,
        "holdings": [h.__dict__ for h in holdings],
        "differences": [d.__dict__ for d in differences],
        "access_expires_at": expires,
        "token_stored": False,
    }
