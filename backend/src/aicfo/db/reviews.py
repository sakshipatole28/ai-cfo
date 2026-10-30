"""Review persistence: agent runs → draft findings → advisor decisions → approval."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aicfo.agents.review import ReviewState
from aicfo.db import audit
from aicfo.db.models import AuditEvent, Client, Finding, Review, ReviewRun, Snapshot, Tenant
from aicfo.db.pipeline import latest_snapshot, money

# The three things an adviser can do with a finding.
DECISIONS = ("accepted", "dismissed", "snoozed")
# The console names one finding per topic ("<client>-tax-timing"); the pipeline names one per
# evidence item ("<client>:lot:MFC:2025-10-28"). Topic → evidence prefix.
CONSOLE_TOPICS = {
    "overlap": "overlap",
    "drift": "drift",
    "tax-timing": "lot",
    "harvest": "tax",
    "concentration": "exposure",
}


# Which decision applies to a stored finding, if any.
def _decision_for(ref: str, client_ref: str, decisions: Mapping[str, str]) -> str | None:
    """Exact pipeline ref first, then the console topic that covers this evidence."""
    # An exact match on the pipeline's finding ref.
    if ref in decisions:
        # Use it.
        return decisions[ref]
    # The evidence kind in the ref, e.g. "lot".
    prefix = ref.removeprefix(f"{client_ref}:").split(":", 1)[0]
    # Try each console topic.
    for topic, evidence in CONSOLE_TOPICS.items():
        # This finding is on that topic and the console decided on it.
        if evidence == prefix and f"{client_ref}-{topic}" in decisions:
            # Use the console's decision.
            return decisions[f"{client_ref}-{topic}"]
    # No decision for this finding.
    return None


# A review waiting for an adviser.
@dataclass(frozen=True)
class PendingReview:
    # Which client.
    client_ref: str
    # Which agent run produced the drafts.
    run_id: str
    # When.
    run_at: str
    # Drafts still undecided.
    open_findings: int


# Store an agent run, its trace and every finding (kept or dropped) and log it.
def record_run(
    session: Session,
    tenant: Tenant,
    client: Client,
    state: ReviewState,
    *,
    model: str,
    trigger: str,
    latency_ms: int,
) -> ReviewRun:
    # The drafts from the LangGraph run.
    drafts = state["drafts"]
    # One row per run: model used, timing, counts and the full trace.
    run = ReviewRun(
        tenant_id=tenant.id,
        client_id=client.id,
        # Link to the snapshot the numbers came from.
        snapshot_id=(snap.id if (snap := latest_snapshot(session, client)) else None),
        profile=state.get("profile", "RIA"),
        model=model,
        trigger=trigger,
        latency_ms=latency_ms,
        kept=sum(d.status == "draft" for d in drafts),
        dropped=sum(d.status == "dropped" for d in drafts),
        trace=[asdict(t) for t in state["trace"]],
        # One row per draft: text, evidence ids, citations and the compliance and verifier results.
        findings=[
            Finding(
                tenant_id=tenant.id,
                ref=d.candidate.id,
                kind=d.candidate.kind,
                severity=d.candidate.severity,
                impact=money(d.candidate.impact),
                text=d.text,
                author=d.author,
                evidence_ids=list(d.candidate.evidence_ids),
                citations=[{k: c[k] for k in ("n", "chunk_id", "doc_id")} for c in d.citations],
                compliance=d.compliance,
                verifier=d.verifier,
                status=d.status,
            )
            for d in drafts
        ],
    )
    # Queue it (findings come with it).
    session.add(run)
    # Write so the run has an id.
    session.flush()
    # Log the run (client id, counts, model) in the audit chain.
    audit.append(
        session,
        tenant.id,
        "agent:review",
        "review.drafted",
        "review_run",
        run.id,
        {"client": client.id, "kept": run.kept, "dropped": run.dropped, "model": model},
    )
    # The stored run.
    return run


# Record an adviser's decision on one finding.
def decide(session: Session, finding: Finding, decision: str, actor: str) -> Finding:
    # Only the three known decisions.
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    # A finding a guard blocked can never be shown, so it cannot be decided.
    if finding.status == "dropped":
        raise ValueError("a finding dropped by a guard cannot be decided")
    # Store it.
    finding.status = decision
    # Log who decided what.
    audit.append(session, finding.tenant_id, actor, f"finding.{decision}", "finding", finding.id)
    # The updated finding.
    return finding


# The newest agent run for a client.
def latest_run(session: Session, client: Client) -> ReviewRun | None:
    # Order by time, newest first.
    return session.scalars(
        select(ReviewRun)
        .where(ReviewRun.client_id == client.id)
        .order_by(ReviewRun.created_at.desc())
        .limit(1)
    ).first()


# Approve a client's review with the adviser's decisions.
def approve(
    session: Session,
    tenant: Tenant,
    client: Client,
    decisions: Mapping[str, str],
    actor: str,
    source: str,
) -> Review:
    """Approve a client's review. `decisions` maps finding refs to accepted/dismissed/snoozed.

    Keys may be pipeline refs or console finding ids; a console decision on a topic (say
    drift) applies to every pipeline finding on that topic in the latest run.
    """
    # Any decision that is not one of the three.
    bad = {v for v in decisions.values() if v not in DECISIONS}
    # Refuse unknown decisions.
    if bad:
        raise ValueError(f"unknown decisions: {sorted(bad)}")
    # Approvals apply to the latest run.
    run = latest_run(session, client)
    # There is a run to update.
    if run:
        # Each finding.
        for f in run.findings:
            # Apply the adviser's decision (never to blocked findings).
            if f.status != "dropped" and (d := _decision_for(f.ref, client.ref, decisions)):
                # Store it.
                f.status = d
    # The approval record: who, when, which run, which decisions.
    review = Review(
        tenant_id=tenant.id,
        client_id=client.id,
        run_id=run.id if run else None,
        approved_by=actor,
        decisions=dict(decisions),
        source=source,
    )
    # Queue it.
    session.add(review)
    # Write so it has an id.
    session.flush()
    # Log the approval (ids and counts only).
    audit.append(
        session,
        tenant.id,
        actor,
        "review.approved",
        "review",
        review.id,
        {"client": client.id, "run": review.run_id, "decisions": len(decisions)},
    )
    # The approval.
    return review


# Clients whose latest review is still waiting for an adviser.
def pending(session: Session, tenant: Tenant) -> list[PendingReview]:
    """Clients whose latest run has open drafts and no approval since that run."""
    # Reviews waiting.
    out = []
    # The firm's clients.
    clients = session.scalars(select(Client).where(Client.tenant_id == tenant.id)).all()
    # Each client.
    for c in clients:
        # Their newest run.
        run = latest_run(session, c)
        # Never reviewed.
        if run is None:
            # Skip.
            continue
        # Has anyone approved since that run?
        approved_after = session.scalar(
            select(func.count(Review.id)).where(
                Review.client_id == c.id, Review.approved_at >= run.created_at
            )
        )
        # Drafts still undecided.
        open_ = sum(f.status == "draft" for f in run.findings)
        # Open drafts and no approval since: it is waiting.
        if open_ and not approved_after:
            # Add it.
            out.append(PendingReview(c.ref, run.id, run.created_at.isoformat(), open_))
    # All waiting reviews.
    return out


# Row counts per table.
def counts(session: Session, tenant_id: str | None = None) -> dict[str, Any]:
    """Row counts per table, for one firm or (tenant_id None) the whole database."""
    # Counts.
    out: dict[str, Any] = {}
    # Each table.
    for name, model in (
        ("clients", Client),
        ("snapshots", Snapshot),
        ("review_runs", ReviewRun),
        ("findings", Finding),
        ("reviews", Review),
        ("audit_events", AuditEvent),
    ):
        # SELECT count(*) FROM table.
        q = select(func.count()).select_from(model)  # SELECT count(*) FROM <table>
        # Limit to one firm when asked.
        if tenant_id is not None:
            # Only this firm's rows.
            q = q.where(model.tenant_id == tenant_id)  # only this firm's rows
        # Store the count.
        out[name] = session.scalar(q)
    # All counts.
    return out
