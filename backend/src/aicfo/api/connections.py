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

# Routes under /v1/connections/dhan.
router = APIRouter(prefix="/v1/connections/dhan", tags=["connections"])
# Recorded Dhan responses for sandbox mode.
FIXTURE = REPO_ROOT / "data" / "synthetic" / "dhan_holdings_sandbox.json"
# Synthetic depository statement to compare against.
STATEMENT = REPO_ROOT / "data" / "synthetic" / "cdsl_statement.json"
# In-flight sign-ins: one-time code → (client, start time). Memory only.
_PENDING: dict[str, tuple[str, float]] = {}  # one-time nonce -> (client_id, created)
# A sign-in link is valid for 10 minutes.
FLOW_TTL = 600


# A fake Dhan server for sandbox mode: no network, no credentials.
def _sandbox_transport() -> httpx.MockTransport:
    # Recorded holdings.
    holdings = json.loads(FIXTURE.read_text())

    # Answer each request like Dhan would.
    def handler(request: httpx.Request) -> httpx.Response:
        # Which endpoint was called.
        path = request.url.path
        # Step 1: consent id.
        if path.endswith("/generate-consent"):
            return httpx.Response(
                200,
                json={
                    "consentAppId": f"sandbox-{secrets.token_hex(4)}",
                    "consentAppStatus": "GENERATED",
                    "status": "success",
                },
            )
        # Step 3: access pass.
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
        # Step 4: holdings.
        if path.endswith("/holdings"):
            # The recorded holdings.
            return httpx.Response(200, json=holdings)
        # Anything else does not exist.
        return httpx.Response(404)

    # Use the fake server.
    return httpx.MockTransport(handler)


# Build the Dhan client for the configured mode.
def _client() -> DhanClient:
    # Settings.
    s = get_settings()
    # Switched off.
    if s.dhan_mode == "off":
        # Service unavailable.
        raise HTTPException(503, "Live broker connection is switched off")
    # Sandbox: fake server.
    if s.dhan_mode == "sandbox":
        return DhanClient(
            "sandbox", "sandbox", "1000000001", httpx.Client(transport=_sandbox_transport())
        )
    # Live mode needs real credentials.
    if not (s.dhan_app_id and s.dhan_app_secret and s.dhan_client_id):
        # Say what is missing.
        raise HTTPException(503, "Dhan API key, secret and client id are not configured")
    # Client for the real Dhan.
    return DhanClient(s.dhan_app_id, s.dhan_app_secret.get_secret_value(), s.dhan_client_id)


# POST /start: begin a connection for a client.
@router.post("/start")
# Returns the page where the client approves on Dhan's own site.
def start(client_id: str, response: Response) -> dict[str, str]:
    # Unknown client.
    if client_id not in load_book().clients:
        # Not found.
        raise HTTPException(404, "client not found")
    # Dhan client.
    dhan = _client()
    # Ask Dhan for a consent id.
    try:
        # Step 1.
        consent = dhan.generate_consent()
    # Dhan failed.
    except DhanError as exc:
        # Bad gateway.
        raise HTTPException(502, str(exc)) from exc
    # A one-time code tying the callback to this browser.
    nonce = secrets.token_urlsafe(24)
    # Remember it.
    _PENDING[nonce] = (client_id, time.time())
    # Store the code in an HttpOnly cookie: scripts cannot read it.
    response.set_cookie(
        "dhan_flow",
        nonce,
        max_age=FLOW_TTL,
        httponly=True,
        samesite="lax",
        secure=get_settings().env == "prod",
    )
    # sandbox, live or off.
    mode = get_settings().dhan_mode
    # Sandbox login page, or Dhan's real one.
    login = (
        f"/v1/connections/dhan/sandbox-login?consentAppId={consent}"
        if mode == "sandbox"
        else DhanClient.login_url(consent)
    )
    # Where to send the client.
    return {"login_url": login, "mode": mode}


# Stand-in for Dhan's login page in sandbox mode.
@router.get("/sandbox-login", include_in_schema=False)
# Immediately "approves".
def sandbox_login(consentAppId: str) -> RedirectResponse:  # noqa: N803 - Dhan's parameter name
    # Only in sandbox mode.
    if get_settings().dhan_mode != "sandbox":
        # Hidden otherwise.
        raise HTTPException(404)
    # Send the browser to the callback.
    return RedirectResponse(
        f"/v1/connections/dhan/callback?tokenId=sandbox-{consentAppId}", status_code=302
    )


# GET /callback: Dhan sends the client back here after approval.
@router.get("/callback")
# Read the holdings once, then forget the token.
def callback(tokenId: str, dhan_flow: str | None = Cookie(default=None)) -> dict[str, Any]:  # noqa: N803
    # Match the cookie to a connection we started (one use only).
    pending = _PENDING.pop(dhan_flow, None) if dhan_flow else None
    # Unknown, reused or expired.
    if pending is None or time.time() - pending[1] > FLOW_TTL:
        raise HTTPException(
            400, "This sign-in link is invalid or expired. Start the connection again."
        )
    # Which client this is for.
    client_id = pending[0]
    # Dhan client.
    dhan = _client()
    # Swap the code for a pass and read holdings.
    try:
        # Step 3.
        access = dhan.consume_consent(tokenId)
        # Step 4.
        holdings = dhan.fetch_holdings(access)
    # Pass rejected.
    except TokenExpiredError as exc:
        # Sign in again.
        raise HTTPException(401, str(exc)) from exc
    # Dhan failed.
    except DhanError as exc:
        # Bad gateway.
        raise HTTPException(502, str(exc)) from exc
    # The client's latest depository statement (ISIN → quantity).
    statement = {
        k: float(v) for k, v in json.loads(STATEMENT.read_text()).get(client_id, {}).items()
    }
    # Compare; nothing is merged silently.
    differences = reconcile(holdings, statement)
    # Remember only when the pass ends.
    expires = access.expires_at
    # Session mode: drop the token now; it is never stored.
    del access  # session mode: the token is not stored anywhere
    # Holdings, differences and the expiry; `token_stored` is always False.
    return {
        "client_id": client_id,
        "holdings": [h.__dict__ for h in holdings],
        "differences": [d.__dict__ for d in differences],
        "access_expires_at": expires,
        "token_stored": False,
    }
