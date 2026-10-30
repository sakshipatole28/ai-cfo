import hashlib
import hmac
import json
from collections.abc import Iterator

import httpx
import pyotp
import pytest
import respx
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from aicfo.agents.review import ReviewPipeline
from aicfo.automation import events
from aicfo.config import get_settings
from aicfo.core.book import load_book
from aicfo.db import audit, migrate, reviews
from aicfo.db.models import AuditEvent, Base, Finding, Position, Snapshot
from aicfo.db.pipeline import demo_tenant, get_client, sync_book
from aicfo.db.session import get_engine, normalise_url
from aicfo.main import create_app
from aicfo.rag.service import get_rag

BOOK = load_book()


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = get_engine()
    migrate.upgrade(eng)
    yield eng
    migrate.downgrade(eng)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s, s.begin():
        yield s


@pytest.fixture(scope="module")
def pipeline() -> ReviewPipeline:
    return ReviewPipeline(get_rag().retriever)


def test_url_normalisation_for_hosted_postgres() -> None:
    assert normalise_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalise_url("postgresql+asyncpg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalise_url("sqlite://") == "sqlite://"


def test_migrations_create_every_table_and_match_models(engine: Engine) -> None:
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"


def test_sync_loads_every_client_and_is_idempotent(session: Session) -> None:
    first = sync_book(session, BOOK)
    assert first.clients_created == len(BOOK.clients) == first.snapshots_created
    again = sync_book(session, BOOK)
    assert (again.clients_created, again.snapshots_created) == (0, 0)
    assert again.snapshots_unchanged == len(BOOK.clients)


def test_snapshot_numbers_come_from_core(session: Session) -> None:
    sync_book(session, BOOK)
    client = get_client(session, demo_tenant(session), "rohan-deshpande")
    assert client is not None
    snap = session.scalars(select(Snapshot).where(Snapshot.client_id == client.id)).one()
    assert round(snap.total) == 2_905_000  # hand-checked in test_core_and_agents
    values = session.scalars(select(Position.value).where(Position.snapshot_id == snap.id)).all()
    assert abs(sum(values) - snap.total) <= len(values) * 0.01


def test_no_personal_data_is_stored(session: Session) -> None:
    sync_book(session, BOOK)
    names = {c.name for c in BOOK.clients.values()}
    dump = json.dumps(
        [
            [str(v) for v in row]
            for t in Base.metadata.sorted_tables
            for row in session.execute(t.select()).all()
        ]
    )
    assert not [n for n in names if n in dump]


def test_review_run_decisions_and_approval(session: Session, pipeline: ReviewPipeline) -> None:
    sync_book(session, BOOK)
    tenant = demo_tenant(session)
    client = get_client(session, tenant, "rohan-deshpande")
    assert client is not None
    state = pipeline.run("rohan-deshpande")
    run = reviews.record_run(
        session, tenant, client, state, model="policy", trigger="api", latency_ms=5
    )
    assert run.kept > 0 and run.snapshot_id is not None
    assert [p.client_ref for p in reviews.pending(session, tenant)] == ["rohan-deshpande"]

    first = next(f for f in run.findings if f.status == "draft")
    reviews.decide(session, first, "accepted", "adviser-1")
    with pytest.raises(ValueError):
        reviews.decide(session, first, "maybe", "adviser-1")

    decisions = {f.ref: "dismissed" for f in run.findings if f.status != "dropped"}
    review = reviews.approve(session, tenant, client, decisions, "adviser-1", "console")
    assert review.run_id == run.id
    assert {f.status for f in run.findings} <= {"dismissed", "dropped"}
    assert reviews.pending(session, tenant) == []


def test_console_finding_ids_map_to_pipeline_findings(
    session: Session, pipeline: ReviewPipeline
) -> None:
    sync_book(session, BOOK)
    tenant = demo_tenant(session)
    client = get_client(session, tenant, "rohan-deshpande")
    assert client is not None
    run = reviews.record_run(
        session,
        tenant,
        client,
        pipeline.run(client.ref),
        model="policy",
        trigger="api",
        latency_ms=1,
    )
    console = {  # ids exactly as frontend/src/lib/engine.ts builds them
        "rohan-deshpande-overlap": "accepted",
        "rohan-deshpande-drift": "snoozed",
        "rohan-deshpande-tax-timing": "accepted",
        "rohan-deshpande-harvest": "dismissed",
        "rohan-deshpande-concentration": "accepted",
    }
    reviews.approve(session, tenant, client, console, "m-arun", "console")
    by_kind = {f.ref.split(":")[1]: f.status for f in run.findings}
    assert by_kind == {
        "overlap": "accepted",
        "drift": "snoozed",
        "lot": "accepted",
        "tax": "dismissed",
        "exposure": "accepted",
    }
    assert all(f.status != "draft" for f in run.findings)


def test_audit_chain_detects_tampering(session: Session) -> None:
    sync_book(session, BOOK)
    sync_book(session, BOOK)
    assert audit.verify(session) == (True, 2)
    tamper = update(AuditEvent).where(AuditEvent.seq == 1).values(actor="someone-else")
    if session.bind.dialect.name == "postgresql":  # type: ignore[union-attr]
        # The append-only trigger refuses the edit outright.
        with pytest.raises(DBAPIError, match="append-only"), session.begin_nested():
            session.execute(tamper)
        return
    session.execute(tamper)
    session.expire_all()
    assert audit.verify(session)[0] is False


# ---------------- API ----------------
@pytest.fixture
def client(engine: Engine) -> TestClient:
    return TestClient(create_app())


def owner_token(client: TestClient, email: str = "owner@firm.example") -> str:
    """Create a firm through the API and finish MFA with a real TOTP code."""
    r = client.post(
        "/v1/auth/firms",
        json={
            "firm_name": "Test Wealth",
            "firm_type": "RIA",
            "registration": "INA000000001",
            "owner_name": "Test Owner",
            "email": email,
            "password": "correct horse battery",
        },
    )
    assert r.status_code == 201, r.text
    code = pyotp.TOTP(r.json()["totp_secret"]).now()
    r = client.post(
        "/v1/auth/mfa/confirm",
        json={"email": email, "password": "correct horse battery", "code": code},
    )
    assert r.status_code == 200, r.text
    return str(r.json()["token"])


def test_api_sync_run_approve_flow(client: TestClient) -> None:
    token = owner_token(client)  # the new firm is seeded with the synthetic book
    auth = {"Authorization": f"Bearer {token}"}
    assert client.post("/v1/pipeline/sync").json()["snapshots_unchanged"] >= len(BOOK.clients)
    run = client.post("/v1/clients/neha-joshi/reviews/run", json={"trigger": "schedule"}).json()
    assert run["model"] == "policy" and run["kept"] >= 1 and run["runs"] == 2  # demo + new firm
    pending = client.get("/v1/reviews/pending", headers=auth).json()
    assert [p["client_ref"] for p in pending] == ["neha-joshi"]  # only this firm's queue

    own = client.post("/v1/clients/neha-joshi/reviews/run", json={}, headers=auth).json()
    draft = next(f for f in own["findings"] if f["status"] == "draft")
    r = client.post(
        f"/v1/findings/{draft['id']}/decision", json={"decision": "accepted"}, headers=auth
    )
    assert r.json()["status"] == "accepted"
    r = client.post(
        "/v1/clients/neha-joshi/reviews/approve",
        json={"decisions": {draft["ref"]: "accepted"}},
        headers=auth,
    )
    assert r.status_code == 200 and r.json()["run_id"] == own["run_id"]
    assert client.get("/v1/reviews/pending", headers=auth).json() == []
    assert client.get("/v1/audit/verify", headers=auth).json()["ok"] is True
    status = client.get("/v1/pipeline/status", headers=auth).json()
    assert status["counts"]["reviews"] == 1 and status["audit_chain_ok"]


def test_console_writes_need_a_signed_in_adviser(client: TestClient) -> None:
    client.post("/v1/pipeline/sync")
    r = client.post("/v1/clients/neha-joshi/reviews/approve", json={"decisions": {}})
    assert r.status_code == 401  # no token
    r = client.post(
        "/v1/clients/neha-joshi/reviews/approve",
        json={},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401  # forged token
    assert client.post("/v1/clients/nobody/reviews/run", json={}).status_code == 404


def test_automation_token_is_enforced(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AICFO_AUTOMATION_TOKEN", "n8n-test-token")
    get_settings.cache_clear()
    try:
        assert client.post("/v1/pipeline/sync").status_code == 401
        ok = client.post("/v1/pipeline/sync", headers={"Authorization": "Bearer n8n-test-token"})
        assert ok.status_code == 200
    finally:
        monkeypatch.delenv("AICFO_AUTOMATION_TOKEN")
        get_settings.cache_clear()


def test_prod_without_automation_token_disables_automation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AICFO_ENV", "prod")
    get_settings.cache_clear()
    try:
        assert client.post("/v1/pipeline/sync").status_code == 503
    finally:
        monkeypatch.setenv("AICFO_ENV", "test")
        get_settings.cache_clear()


# ---------------- n8n events ----------------
@respx.mock
def test_webhook_is_signed_and_carries_ids_only() -> None:
    route = respx.post("https://n8n.example.test/webhook/aicfo").mock(
        return_value=httpx.Response(200)
    )
    events.WebhookSink("https://n8n.example.test/webhook/aicfo", "s3cret").emit(
        "review.approved", {"client": "neha-joshi", "review_id": "r1"}
    )
    req = route.calls.last.request
    sig = hmac.new(b"s3cret", req.content, hashlib.sha256).hexdigest()
    assert req.headers["X-AICFO-Signature"] == f"sha256={sig}"
    assert json.loads(req.content)["data"] == {"client": "neha-joshi", "review_id": "r1"}


@respx.mock
def test_webhook_failure_never_raises() -> None:
    respx.post("https://n8n.example.test/x").mock(side_effect=httpx.ConnectError("down"))
    events.WebhookSink("https://n8n.example.test/x").emit("review.drafted", {"client": "c"})


def test_findings_keep_the_client_placeholder(session: Session, pipeline: ReviewPipeline) -> None:
    sync_book(session, BOOK)
    tenant = demo_tenant(session)
    c = get_client(session, tenant, "rohan-deshpande")
    assert c is not None
    reviews.record_run(
        session, tenant, c, pipeline.run(c.ref), model="policy", trigger="api", latency_ms=1
    )
    texts = session.scalars(select(Finding.text)).all()
    assert texts and all("Rohan" not in t for t in texts)
