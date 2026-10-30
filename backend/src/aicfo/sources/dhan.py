"""Live, read-only connection to a client's Dhan account (DhanHQ API v2).

Flow (individual API key mode, per Dhan's documentation):
  1. generate_consent()  POST auth.dhan.co/app/generate-consent      → consentAppId
  2. login_url()         the client signs in on Dhan's own page        → redirect with tokenId
  3. consume_consent()   GET  auth.dhan.co/app/consumeApp-consent      → 24-hour access token
  4. fetch_holdings()    GET  api.dhan.co/v2/holdings                  → ISIN, quantity, average cost

Safety by construction:
  * Only the URLs in ALLOWED are ever requested; there is no code path to order endpoints.
  * The client's name and trading code returned by Dhan are discarded immediately.
  * The access token is returned to the caller and never logged; session mode discards it after one sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

# Dhan's sign-in service.
AUTH = "https://auth.dhan.co"
# Dhan's data API (version 2).
API = "https://api.dhan.co/v2"
# The ONLY addresses this code may call. All are read-only; there is no order endpoint here.
ALLOWED = frozenset(
    {
        f"{AUTH}/app/generate-consent",
        f"{AUTH}/app/consumeApp-consent",
        f"{API}/holdings",
        f"{API}/positions",
    }
)


# The connection failed; the message never contains a token.
class DhanError(RuntimeError):
    """The connection failed; the message is safe to show (no tokens)."""


# The 24-hour token ended; the client must sign in again.
class TokenExpiredError(DhanError):
    """The 24-hour access token is no longer valid; the client must sign in again."""


# The temporary pass Dhan gives after the client approves.
@dataclass(frozen=True)
class AccessPass:
    # The access token (secret).
    token: str
    # Dhan client id, only to label the connection.
    client_ref: str  # Dhan client id, kept only to label the connection
    # When the pass ends.
    expires_at: str  # ISO timestamp (IST) as returned by Dhan

    # Printing a pass must never reveal the token.
    def __repr__(self) -> str:  # never print the token
        # Token shown as ***.
        return (
            f"AccessPass(client_ref={self.client_ref!r}, expires_at={self.expires_at!r}, token=***)"
        )


# One holding as Dhan reports it.
@dataclass(frozen=True)
class BrokerHolding:
    # Security code.
    isin: str
    # Ticker.
    symbol: str
    # Total shares.
    quantity: float
    # Shares already settled in the demat account.
    settled_quantity: float
    # Shares still settling (T+1).
    pending_quantity: float
    # Average buy price.
    average_cost: float
    # Where the data came from.
    source: str = "Dhan"


# Talks to Dhan on the client's behalf, read-only.
class DhanClient:
    # Our app's credentials and the client's Dhan id.
    def __init__(
        self, app_id: str, app_secret: str, client_id: str, http: httpx.Client | None = None
    ) -> None:
        # Identify our app to Dhan.
        self._app_headers = {"app_id": app_id, "app_secret": app_secret}
        # The client's Dhan id.
        self.client_id = client_id
        # HTTP client (tests pass a mocked one).
        self._http = http or httpx.Client(timeout=15.0)

    # The only way this class talks to Dhan.
    # Every call goes through here, so the safety rules apply to all of them.
    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        # Refuse any address that is not on the read-only list.
        if url not in ALLOWED:
            # Fail loudly.
            raise DhanError(f"blocked: {url} is not an allowed read-only endpoint")
        # Last error, for the final message.
        last: Exception | None = None
        # Up to three tries.
        for _attempt in range(3):
            # Send the request.
            try:
                # One HTTP call.
                r = self._http.request(method, url, params=params, headers=headers)
            # Network blip: try again.
            except httpx.TransportError as exc:  # network blip: retry
                # Remember it.
                last = exc
                # Next attempt.
                continue
            # Token expired or revoked.
            if r.status_code in (401, 403):
                # Ask the client to sign in again.
                raise TokenExpiredError(
                    "Dhan access has expired or was revoked; ask the client to sign in again"
                )
            # Dhan's server problem: try again.
            if r.status_code >= 500:
                # Remember it.
                last = DhanError(f"Dhan returned {r.status_code}")
                continue
            # Our request was rejected: retrying will not help.
            if r.status_code >= 400:
                # Stop.
                raise DhanError(f"Dhan rejected the request ({r.status_code})")
            # Success.
            return r.json()
        # Three failures in a row.
        raise DhanError("Dhan did not respond after 3 attempts") from last

    # Step 1: ask Dhan for a consent id.
    def generate_consent(self) -> str:
        # POST to the consent endpoint with our app's credentials.
        body = self._request(
            "POST",
            f"{AUTH}/app/generate-consent",
            params={"client_id": self.client_id},
            headers=self._app_headers,
        )
        # The consent id from the reply.
        consent = body.get("consentAppId") if isinstance(body, dict) else None
        # Dhan did not give one.
        if not consent:
            # Stop.
            raise DhanError("Dhan did not return a consent id")
        # The consent id.
        return str(consent)

    # Step 2: the page where the client signs in on Dhan's own site.
    @staticmethod
    # We never see their password or PIN.
    def login_url(consent_id: str) -> str:
        # Address to send the client to.
        return f"{AUTH}/login/consentApp-login?{urlencode({'consentAppId': consent_id})}"

    # Step 3: swap the one-time tokenId for a 24-hour access pass.
    def consume_consent(self, token_id: str) -> AccessPass:
        # GET the consent result.
        body = self._request(
            "GET",
            f"{AUTH}/app/consumeApp-consent",
            params={"tokenId": token_id},
            headers=self._app_headers,
        )
        # Check the reply has a token.
        if not isinstance(body, dict) or not body.get("accessToken"):
            # Stop.
            raise DhanError("Dhan did not return an access token")
        # dhanClientName / dhanClientUcc are personal data we do not need: dropped here.
        # Keep only the token, id and expiry; the name and trading code are discarded.
        return AccessPass(
            token=str(body["accessToken"]),
            client_ref=str(body.get("dhanClientId", "")),
            expires_at=str(body.get("expiryTime", "")),
        )

    # Step 4: read the client's holdings.
    def fetch_holdings(self, access: AccessPass) -> list[BrokerHolding]:
        # GET /holdings with the access pass.
        rows = self._request(
            "GET",
            f"{API}/holdings",
            headers={"access-token": access.token, "Content-Type": "application/json"},
        )
        # Unexpected reply shape.
        if not isinstance(rows, list):
            # Stop.
            raise DhanError("unexpected holdings response")
        # Convert each row.
        return [normalise(r) for r in rows]


# Convert Dhan's JSON row into a BrokerHolding.
def normalise(row: dict[str, Any]) -> BrokerHolding:
    # Missing fields raise an error.
    try:
        # Map Dhan's field names to ours.
        return BrokerHolding(
            isin=str(row["isin"]),
            symbol=str(row.get("tradingSymbol", "")),
            quantity=float(row["totalQty"]),
            settled_quantity=float(row.get("dpQty", row["totalQty"])),
            pending_quantity=float(row.get("t1Qty", 0)),
            average_cost=float(row["avgCostPrice"]),
        )
    # A holding without ISIN, quantity or cost.
    except (KeyError, TypeError, ValueError) as exc:
        # Stop.
        raise DhanError("a holding was missing ISIN, quantity or average cost") from exc


# One mismatch between the broker and the statement.
@dataclass(frozen=True)
class Difference:
    # Security code.
    isin: str
    # Ticker.
    symbol: str
    # Quantity at the broker (None if absent).
    broker_quantity: float | None
    # Quantity in the depository statement (None if absent).
    statement_quantity: float | None
    # Explanation for the adviser.
    note: str


# Compare live broker holdings with the latest depository statement.
def reconcile(broker: list[BrokerHolding], statement: dict[str, float]) -> list[Difference]:
    """Compare live broker quantities with the latest depository statement (by ISIN).

    Nothing is merged silently: every mismatch becomes a difference for the adviser to resolve.
    """
    # Differences found.
    out: list[Difference] = []
    # ISINs found at the broker.
    seen = set()
    # Each broker holding.
    for h in broker:
        # Remember it.
        seen.add(h.isin)
        # Quantity in the statement.
        s = statement.get(h.isin)
        # Not in the statement…
        if s is None:
            # …report it.
            out.append(
                Difference(
                    h.isin,
                    h.symbol,
                    h.quantity,
                    None,
                    "Only in the live broker data (bought after the statement?)",
                )
            )
        # Quantities differ…
        elif abs(s - h.quantity) > 1e-6:
            # …perhaps because some shares are still settling.
            hint = (
                " The live figure includes shares still settling."
                if h.pending_quantity and abs(s - h.settled_quantity) < 1e-6
                else ""
            )
            # Report the difference.
            out.append(Difference(h.isin, h.symbol, h.quantity, s, f"Quantities differ.{hint}"))
    # Statement holdings not seen at the broker.
    for isin, qty in statement.items():
        # Missing at the broker…
        if isin not in seen:
            # …report it.
            out.append(
                Difference(
                    isin,
                    "",
                    None,
                    qty,
                    "In the statement but not at the broker (sold, or held elsewhere?)",
                )
            )
    # All differences; nothing is merged silently.
    return out


# Hours left on the access pass.
def expires_in_hours(access: AccessPass, now: datetime) -> float | None:
    # Parse the expiry time.
    try:
        # Expiry as a datetime.
        exp = datetime.fromisoformat(access.expires_at)
    # Unreadable expiry.
    except ValueError:
        # Unknown.
        return None
    # Compare like with like (both naive or both aware).
    if exp.tzinfo is None and now.tzinfo is not None:
        # Drop the timezone.
        now = now.replace(tzinfo=None)
    # Hours remaining.
    return (exp - now).total_seconds() / 3600
