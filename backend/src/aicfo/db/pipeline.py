"""Data pipeline: synthetic book → core maths → Postgres.

    book.json ──▶ core.snapshot (positions, allocation, drift) ──▶ clients · snapshots · positions

Idempotent: a snapshot is keyed by a hash of its inputs, so re-running the sync (n8n does
it on a schedule) writes nothing new until the holdings, prices or engine change.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from aicfo.core.analytics import snapshot
from aicfo.core.book import Book, load_book
from aicfo.db import audit
from aicfo.db.models import Client, Position, Snapshot, Tenant

# The synthetic demo firm shown in the console.
# The synthetic demo firm that always exists (so scheduled syncs have something to refresh).
DEMO_TENANT = {"slug": "anand-wealth", "display_name": "Anand Wealth (demo)", "firm_type": "RIA"}


# What a sync did, for logs and the audit trail.
@dataclass(frozen=True)
class SyncReport:
    # New clients added.
    clients_created: int
    # New snapshots written.
    snapshots_created: int
    # Clients whose inputs had not changed (nothing written).
    snapshots_unchanged: int


# Convert a float to an exact 2-decimal Decimal for the database.
def money(x: float) -> Decimal:
    # Via str() so binary float noise does not leak in.
    return Decimal(str(round(x, 2)))


# The demo firm, created on first use.
def demo_tenant(session: Session) -> Tenant:
    # Look it up by its slug.
    t = session.scalars(select(Tenant).where(Tenant.slug == DEMO_TENANT["slug"])).first()
    # First run: create it.
    if t is None:
        # Build the firm row…
        t = Tenant(**DEMO_TENANT)
        # …and queue it for saving.
        session.add(t)
        # Write now so the firm has an id.
        session.flush()
    # The firm.
    return t


# A client of a firm by its pseudonymous reference, or None.
def get_client(session: Session, tenant: Tenant, ref: str) -> Client | None:
    # Match both the firm and the reference, so firms never see each other's clients.
    return session.scalars(
        select(Client).where(Client.tenant_id == tenant.id, Client.ref == ref)
    ).first()


# The client's most recent snapshot, or None.
def latest_snapshot(session: Session, client: Client) -> Snapshot | None:
    # Newest first, take one.
    return session.scalars(
        select(Snapshot)
        .where(Snapshot.client_id == client.id)
        .order_by(Snapshot.created_at.desc())
        .limit(1)
    ).first()


# A fingerprint of everything a snapshot depends on.
def _inputs_hash(book: Book, ref: str, engine: str) -> str:
    # The client's holdings and risk.
    spec = book.client(ref)
    # Holdings as plain data.
    holdings = [asdict(h) for h in spec.holdings]
    # Today's price or NAV of each holding.
    prices = {
        h.ref: (book.funds[h.ref].nav if h.kind == "fund" else book.stocks[h.ref].price)
        for h in spec.holdings
    }
    # Stable JSON of date, engine version, risk, holdings and prices.
    payload = json.dumps(
        {"today": book.today, "engine": engine, "risk": spec.risk, "h": holdings, "p": prices},
        sort_keys=True,
        default=str,
    )
    # If this is unchanged, the snapshot would be identical.
    return hashlib.sha256(payload.encode()).hexdigest()


# Load the synthetic book into one firm, or into every firm.
def sync_book(
    session: Session,
    book: Book | None = None,
    actor: str = "system",
    tenant: Tenant | None = None,
) -> SyncReport:
    """Load the book into one firm (`tenant`), or into the demo firm and every other firm."""
    # Default to the shared synthetic book.
    book = book or load_book()  # the synthetic book shared with the console
    # No firm given: this is the scheduled sync, so refresh all firms.
    if tenant is None:  # scheduled sync (n8n): every firm gets refreshed
        # Make sure the demo firm exists.
        demo_tenant(session)  # make sure the demo firm exists
        # Sync each firm in turn.
        reports = [
            sync_book(session, book, actor, t) for t in session.scalars(select(Tenant)).all()
        ]
        # Combine into one report.
        return SyncReport(  # one combined report across firms
            sum(r.clients_created for r in reports),
            sum(r.snapshots_created for r in reports),
            sum(r.snapshots_unchanged for r in reports),
        )
    # Counters.
    created = new_snaps = same = 0
    # Each client in the book.
    for ref, spec in book.clients.items():
        # Does the firm already have this client?
        client = get_client(session, tenant, ref)
        # No: add them.
        if client is None:
            # Pseudonymous reference and risk profile only: no name.
            client = Client(tenant_id=tenant.id, ref=ref, risk=spec.risk)
            # Queue it.
            session.add(client)
            # Write now so the client has an id.
            session.flush()
            # Count it.
            created += 1
        # Keep the risk profile current.
        client.risk = spec.risk

        # Compute everything with the deterministic core.
        s = snapshot(ref, book)
        # Fingerprint of the inputs.
        h = _inputs_hash(book, ref, s.engine_version)
        # Already have a snapshot with this fingerprint?
        exists = session.scalars(
            select(Snapshot.id).where(Snapshot.client_id == client.id, Snapshot.inputs_hash == h)
        ).first()
        # Yes: nothing changed.
        if exists:
            # Count it.
            same += 1
            # Next client.
            continue
        # Store the totals, allocation, drift and every position (security names only).
        snap = Snapshot(
            tenant_id=tenant.id,
            client_id=client.id,
            as_of=s.today,
            engine_version=s.engine_version,
            inputs_hash=h,
            total=money(s.total),
            allocation_pct={k: round(v, 4) for k, v in s.allocation_pct.items()},
            drift={k: round(v, 4) for k, v in s.drift.items()},
            look_through_pct=Decimal(str(round(s.look_through_pct, 2))),
            positions=[
                Position(
                    tenant_id=tenant.id,
                    ref=p.ref,
                    kind=p.kind,
                    name=p.name,
                    asset_class=p.asset_class,
                    source=p.source,
                    units=Decimal(str(round(p.units, 4))),
                    value=money(p.value),
                )
                for p in s.positions
            ],
        )
        # Queue it.
        session.add(snap)
        # Count it.
        new_snaps += 1
    # Summarise.
    report = SyncReport(created, new_snaps, same)
    # Record the sync in the tamper-evident audit log (counts only).
    audit.append(session, tenant.id, actor, "pipeline.sync", "tenant", tenant.id, asdict(report))
    # Done.
    return report
