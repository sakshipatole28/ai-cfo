import csv
import io
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from aicfo.config import REPO_ROOT
from aicfo.ingest.anonymise import anonymise_rows, classify
from aicfo.main import create_app
from aicfo.sources.dhan import (
    ALLOWED,
    API,
    AUTH,
    AccessPass,
    BrokerHolding,
    DhanClient,
    DhanError,
    TokenExpiredError,
    reconcile,
)

HOLDINGS = json.loads((REPO_ROOT / "data" / "synthetic" / "dhan_holdings_sandbox.json").read_text())


def client() -> DhanClient:
    return DhanClient("app-key", "app-secret", "1000000001", httpx.Client())


# ---------------- connector ----------------
@respx.mock
def test_full_consent_flow_and_holdings() -> None:
    gen = respx.post(f"{AUTH}/app/generate-consent").respond(
        json={"consentAppId": "c-1", "status": "success"}
    )
    respx.get(f"{AUTH}/app/consumeApp-consent").respond(
        json={
            "dhanClientId": "1000000001",
            "dhanClientName": "SOME PERSON",
            "dhanClientUcc": "U1",
            "accessToken": "tok-123",
            "expiryTime": "2026-10-20T09:00:00",
        }
    )
    hold = respx.get(f"{API}/holdings").respond(json=HOLDINGS)
    dhan = client()
    consent = dhan.generate_consent()
    assert consent == "c-1"
    assert gen.calls[0].request.headers["app_id"] == "app-key"
    assert "consentAppId=c-1" in dhan.login_url(consent)
    access = dhan.consume_consent("token-id")
    assert "SOME PERSON" not in repr(access) and "tok-123" not in repr(access)
    rows = dhan.fetch_holdings(access)
    assert hold.calls[0].request.headers["access-token"] == "tok-123"
    assert {r.isin for r in rows} >= {"INE040A01034", "INE009A01021"}
    infy = next(r for r in rows if r.symbol == "INFY")
    assert (infy.quantity, infy.settled_quantity, infy.pending_quantity) == (80, 75, 5)


def test_only_read_only_endpoints_are_reachable() -> None:
    assert all("order" not in u for u in ALLOWED)
    with pytest.raises(DhanError, match="blocked"):
        client()._request("POST", f"{API}/orders")


@respx.mock
def test_expired_token_is_reported_clearly() -> None:
    respx.get(f"{API}/holdings").respond(401)
    with pytest.raises(TokenExpiredError):
        client().fetch_holdings(AccessPass("t", "1", ""))


@respx.mock
def test_server_errors_are_retried_then_succeed() -> None:
    route = respx.get(f"{API}/holdings")
    route.side_effect = [httpx.Response(503), httpx.Response(200, json=HOLDINGS)]
    assert len(client().fetch_holdings(AccessPass("t", "1", ""))) == len(HOLDINGS)
    assert route.call_count == 2


@respx.mock
def test_malformed_holding_is_rejected() -> None:
    respx.get(f"{API}/holdings").respond(json=[{"tradingSymbol": "X"}])
    with pytest.raises(DhanError, match="missing"):
        client().fetch_holdings(AccessPass("t", "1", ""))


def test_reconcile_flags_every_difference() -> None:
    broker = [
        BrokerHolding("INE009A01021", "INFY", 80, 75, 5, 1500),
        BrokerHolding("INE040A01034", "HDFCBANK", 120, 120, 0, 1200),
        BrokerHolding("INE000NEW001", "NEW", 10, 10, 0, 100),
    ]
    diffs = {
        d.symbol or d.isin: d
        for d in reconcile(broker, {"INE009A01021": 75, "INE040A01034": 120, "INE000OLD001": 5})
    }
    assert "settling" in diffs["INFY"].note
    assert "HDFCBANK" not in diffs
    assert diffs["NEW"].statement_quantity is None
    assert diffs["INE000OLD001"].broker_quantity is None


# ---------------- API (sandbox mode) ----------------
def test_sandbox_flow_end_to_end() -> None:
    api = TestClient(create_app())
    start = api.post("/v1/connections/dhan/start", params={"client_id": "rohan-deshpande"})
    assert start.status_code == 200 and start.json()["mode"] == "sandbox"
    result = api.get(
        start.json()["login_url"]
    )  # follows the sandbox sign-in redirect to the callback
    body = result.json()
    assert result.status_code == 200 and body["token_stored"] is False
    assert len(body["holdings"]) == 4
    assert [d["symbol"] for d in body["differences"]] == ["INFY"]
    # the one-time link cannot be replayed
    assert api.get(start.json()["login_url"]).status_code == 400


def test_callback_without_flow_cookie_is_rejected() -> None:
    assert (
        TestClient(create_app())
        .get("/v1/connections/dhan/callback", params={"tokenId": "x"})
        .status_code
        == 400
    )


# ---------------- anonymiser ----------------
def _sample() -> list[dict[str, str]]:
    text = (REPO_ROOT / "data" / "synthetic" / "ca_firm_sample.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def test_identity_columns_are_removed_and_codes_are_stable() -> None:
    out, rep = anonymise_rows(_sample(), b"firm-secret")
    flat = json.dumps(out)
    for secret in (
        "Asha",
        "ABCPV1234K",
        "9876501234",
        "asha.v@example.com",
        "1234567/89",
        "9123409876",
    ):
        assert secret not in flat
    assert rep.clients == 2
    assert out[0]["client_code"] == out[1]["client_code"]  # same client, same code
    assert out[0]["ISIN"] == "INF0DEMO0001" and out[0]["Units"] == "1850.25"
    assert rep.scrubbed_cells == 1  # phone number hidden inside the remarks column


def test_codes_depend_on_the_firms_key() -> None:
    a, _ = anonymise_rows(_sample(), b"key-one")
    b, _ = anonymise_rows(_sample(), b"key-two")
    assert a[0]["client_code"] != b[0]["client_code"]


@pytest.mark.parametrize(
    ("header", "kind"),
    [
        ("Client name", "name"),
        ("PAN", "pan"),
        ("Mobile", "phone"),
        ("Email ID", "email"),
        ("Folio number", "account"),
        ("ISIN", None),
        ("Units", None),
    ],
)
def test_column_classification(header: str, kind: str | None) -> None:
    assert classify(header) == kind


def test_key_is_required() -> None:
    with pytest.raises(ValueError):
        anonymise_rows(_sample(), b"")
