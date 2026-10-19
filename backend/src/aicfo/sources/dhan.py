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

AUTH = "https://auth.dhan.co"
API = "https://api.dhan.co/v2"
ALLOWED = frozenset(
    {
        f"{AUTH}/app/generate-consent",
        f"{AUTH}/app/consumeApp-consent",
        f"{API}/holdings",
        f"{API}/positions",
    }
)


class DhanError(RuntimeError):
    """The connection failed; the message is safe to show (no tokens)."""


class TokenExpiredError(DhanError):
    """The 24-hour access token is no longer valid; the client must sign in again."""


@dataclass(frozen=True)
class AccessPass:
    token: str
    client_ref: str  # Dhan client id, kept only to label the connection
    expires_at: str  # ISO timestamp (IST) as returned by Dhan

    def __repr__(self) -> str:  # never print the token
        return (
            f"AccessPass(client_ref={self.client_ref!r}, expires_at={self.expires_at!r}, token=***)"
        )


@dataclass(frozen=True)
class BrokerHolding:
    isin: str
    symbol: str
    quantity: float
    settled_quantity: float
    pending_quantity: float
    average_cost: float
    source: str = "Dhan"


class DhanClient:
    def __init__(
        self, app_id: str, app_secret: str, client_id: str, http: httpx.Client | None = None
    ) -> None:
        self._app_headers = {"app_id": app_id, "app_secret": app_secret}
        self.client_id = client_id
        self._http = http or httpx.Client(timeout=15.0)

    # The only way this class talks to Dhan.
    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        if url not in ALLOWED:
            raise DhanError(f"blocked: {url} is not an allowed read-only endpoint")
        last: Exception | None = None
        for _attempt in range(3):
            try:
                r = self._http.request(method, url, params=params, headers=headers)
            except httpx.TransportError as exc:  # network blip: retry
                last = exc
                continue
            if r.status_code in (401, 403):
                raise TokenExpiredError(
                    "Dhan access has expired or was revoked; ask the client to sign in again"
                )
            if r.status_code >= 500:
                last = DhanError(f"Dhan returned {r.status_code}")
                continue
            if r.status_code >= 400:
                raise DhanError(f"Dhan rejected the request ({r.status_code})")
            return r.json()
        raise DhanError("Dhan did not respond after 3 attempts") from last

    def generate_consent(self) -> str:
        body = self._request(
            "POST",
            f"{AUTH}/app/generate-consent",
            params={"client_id": self.client_id},
            headers=self._app_headers,
        )
        consent = body.get("consentAppId") if isinstance(body, dict) else None
        if not consent:
            raise DhanError("Dhan did not return a consent id")
        return str(consent)

    @staticmethod
    def login_url(consent_id: str) -> str:
        return f"{AUTH}/login/consentApp-login?{urlencode({'consentAppId': consent_id})}"

    def consume_consent(self, token_id: str) -> AccessPass:
        body = self._request(
            "GET",
            f"{AUTH}/app/consumeApp-consent",
            params={"tokenId": token_id},
            headers=self._app_headers,
        )
        if not isinstance(body, dict) or not body.get("accessToken"):
            raise DhanError("Dhan did not return an access token")
        # dhanClientName / dhanClientUcc are personal data we do not need: dropped here.
        return AccessPass(
            token=str(body["accessToken"]),
            client_ref=str(body.get("dhanClientId", "")),
            expires_at=str(body.get("expiryTime", "")),
        )

    def fetch_holdings(self, access: AccessPass) -> list[BrokerHolding]:
        rows = self._request(
            "GET",
            f"{API}/holdings",
            headers={"access-token": access.token, "Content-Type": "application/json"},
        )
        if not isinstance(rows, list):
            raise DhanError("unexpected holdings response")
        return [normalise(r) for r in rows]


def normalise(row: dict[str, Any]) -> BrokerHolding:
    try:
        return BrokerHolding(
            isin=str(row["isin"]),
            symbol=str(row.get("tradingSymbol", "")),
            quantity=float(row["totalQty"]),
            settled_quantity=float(row.get("dpQty", row["totalQty"])),
            pending_quantity=float(row.get("t1Qty", 0)),
            average_cost=float(row["avgCostPrice"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DhanError("a holding was missing ISIN, quantity or average cost") from exc


@dataclass(frozen=True)
class Difference:
    isin: str
    symbol: str
    broker_quantity: float | None
    statement_quantity: float | None
    note: str


def reconcile(broker: list[BrokerHolding], statement: dict[str, float]) -> list[Difference]:
    """Compare live broker quantities with the latest depository statement (by ISIN).

    Nothing is merged silently: every mismatch becomes a difference for the adviser to resolve.
    """
    out: list[Difference] = []
    seen = set()
    for h in broker:
        seen.add(h.isin)
        s = statement.get(h.isin)
        if s is None:
            out.append(
                Difference(
                    h.isin,
                    h.symbol,
                    h.quantity,
                    None,
                    "Only in the live broker data (bought after the statement?)",
                )
            )
        elif abs(s - h.quantity) > 1e-6:
            hint = (
                " The live figure includes shares still settling."
                if h.pending_quantity and abs(s - h.settled_quantity) < 1e-6
                else ""
            )
            out.append(Difference(h.isin, h.symbol, h.quantity, s, f"Quantities differ.{hint}"))
    for isin, qty in statement.items():
        if isin not in seen:
            out.append(
                Difference(
                    isin,
                    "",
                    None,
                    qty,
                    "In the statement but not at the broker (sold, or held elsewhere?)",
                )
            )
    return out


def expires_in_hours(access: AccessPass, now: datetime) -> float | None:
    try:
        exp = datetime.fromisoformat(access.expires_at)
    except ValueError:
        return None
    if exp.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    return (exp - now).total_seconds() / 3600
