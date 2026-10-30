"""CLI: `uv run python -m aicfo.db {migrate|seed|status|downgrade}`.

`seed` loads the synthetic book through the pipeline and runs one review per client, so a
fresh database shows a filled review inbox.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict

from sqlalchemy.orm import Session

from aicfo.agents.service import get_pipeline
from aicfo.db import audit, migrate, reviews
from aicfo.db.pipeline import demo_tenant, get_client, sync_book
from aicfo.db.session import get_engine


# Fill a database with the synthetic book and one review per client.
def seed(session: Session, with_reviews: bool = True) -> None:
    # Load clients and snapshots.
    report = sync_book(session, actor="seed")
    # Show what changed.
    print(f"pipeline: {asdict(report)}")
    # --no-reviews: data only.
    if not with_reviews:
        # Done.
        return
    # The demo firm and the review pipeline.
    tenant, pipeline = demo_tenant(session), get_pipeline()
    # Model name stored with each run.
    model = pipeline.llm.name if pipeline.llm else "policy"
    # Every client in the book.
    for ref in pipeline.book.clients:
        # Their row.
        client = get_client(session, tenant, ref)
        # sync_book just created it.
        assert client is not None
        # Already reviewed: skip, so seeding twice is harmless.
        if reviews.latest_run(session, client):
            # Next client.
            continue
        # Time the run.
        t0 = time.perf_counter()
        # Run the agents.
        state = pipeline.run(ref)
        # Elapsed milliseconds.
        ms = round((time.perf_counter() - t0) * 1000)
        # Store the run and its findings.
        run = reviews.record_run(
            session, tenant, client, state, model=model, trigger="manual", latency_ms=ms
        )
        # Progress line.
        print(f"review {ref:<20} kept {run.kept} dropped {run.dropped} ({model})")


# Command-line entry.
def main() -> None:
    # Argument parser.
    ap = argparse.ArgumentParser(prog="python -m aicfo.db")
    # migrate / downgrade / seed / status.
    sub = ap.add_subparsers(dest="cmd", required=True)
    # Create or update the tables.
    sub.add_parser("migrate")
    # Remove all tables (development only).
    sub.add_parser("downgrade")
    # Load the synthetic data.
    s = sub.add_parser("seed")
    # Skip the agent runs.
    s.add_argument("--no-reviews", action="store_true", help="load data only, skip agent runs")
    # Show row counts and audit-chain health.
    sub.add_parser("status")
    # Read the command line.
    args = ap.parse_args()
    # Connect using AICFO_DATABASE_URL.
    engine = get_engine()

    # Apply migrations.
    if args.cmd == "migrate":
        # Alembic: upgrade to the latest revision.
        migrate.upgrade(engine)
        # Confirm.
        print("migrated to head")
    # Roll everything back.
    elif args.cmd == "downgrade":
        # Alembic: back to empty.
        migrate.downgrade(engine)
        # Confirm.
        print("downgraded to base")
    # seed or status.
    else:
        # One transaction.
        with Session(engine) as session, session.begin():
            # Seed first.
            if args.cmd == "seed":
                # Load data.
                seed(session, with_reviews=not args.no_reviews)
            # Check the chain.
            ok, n = audit.verify(session)
            # Row counts.
            print(f"rows: {reviews.counts(session)}")
            # Intact or broken.
            print(f"audit chain: {'intact' if ok else 'BROKEN'} ({n} events)")


# Run when executed as a program.
if __name__ == "__main__":
    # Go.
    main()
