"""Persisted workflow: pipeline sync, review runs, decisions, approvals and the audit chain.

Who may call what:
  * n8n (automation token) runs the schedule across every firm: sync, review runs, pending list.
  * Signed-in members act inside their own firm, limited by their role's capabilities.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from aicfo.agents.service import get_pipeline
from aicfo.auth.deps import Caller, automation_or, needs
from aicfo.automation.events import get_sink
from aicfo.db import audit, reviews
from aicfo.db.models import Client, Finding, Tenant, User
from aicfo.db.pipeline import get_client, sync_book
from aicfo.db.session import get_session

# All routes live under /v1.
router = APIRouter(prefix="/v1", tags=["workspace"])
# What an adviser can do with a finding.
DecisionName = Literal["accepted", "dismissed", "snoozed"]
# A database session; one transaction per request.
DB = Annotated[Session, Depends(get_session)]  # one transaction per request


# Body of "run a review".
class RunIn(BaseModel):
    # RIA, or MFD (distributor: advice-like text is blocked).
    profile: Literal["RIA", "MFD"] = "RIA"  # MFD blocks advice-like text (distributors)
    # Why it ran; stored with the run.
    trigger: Literal["manual", "schedule", "api"] = "api"  # recorded with the run


# Body of "decide on a finding".
class DecisionIn(BaseModel):
    # accepted, dismissed or snoozed.
    decision: DecisionName


# Body of "approve a review".
class ApproveIn(BaseModel):
    # Finding refs (pipeline or console ids) → the advisor's decision on each.
    # The adviser's decision per finding.
    decisions: dict[str, DecisionName] = Field(default_factory=dict, max_length=200)


# Which firms a caller acts on.
def _firms(session: Session, caller: Caller) -> list[Tenant]:
    """The firms this caller acts on: every firm for automation, their own for a member."""
    # Automation (n8n) covers every firm…
    if caller.user is None:
        # …all of them.
        return list(session.scalars(select(Tenant)).all())
    # A person acts only on their own firm.
    firm = session.get(Tenant, caller.user.tenant_id)
    # Just that firm.
    return [firm] if firm else []


# A client of the signed-in person's firm.
def _own_client(session: Session, user: User, ref: str) -> tuple[Tenant, Client]:
    """A client of the signed-in member's firm (other firms' clients look like 404)."""
    # Their firm.
    firm = session.get(Tenant, user.tenant_id)
    # Look the client up inside that firm only.
    client = get_client(session, firm, ref) if firm else None
    # Other firms' clients look like they do not exist.
    if firm is None or client is None:
        # Not found.
        raise HTTPException(404, "client not found")
    # The firm and client.
    return firm, client


# POST /v1/pipeline/sync: refresh snapshots from the synthetic book.
@router.post("/pipeline/sync")
# n8n weekly, or an Owner on demand.
def pipeline_sync(
    session: DB, caller: Annotated[Caller, Depends(automation_or("settings"))]
) -> dict[str, int]:
    """Refresh snapshots from the synthetic book (n8n weekly, or an Owner on demand)."""
    # Automation: every firm.
    if caller.user is None:  # automation: every firm
        # Counts of what changed.
        return asdict(sync_book(session, actor=caller.actor))
    # A person: their own firm.
    firm = session.get(Tenant, caller.user.tenant_id)
    # Counts of what changed.
    return asdict(sync_book(session, actor=caller.actor, tenant=firm))


# GET /v1/pipeline/status: row counts and audit-chain health.
@router.get("/pipeline/status")
# Open to automation and to roles that may read the audit.
def pipeline_status(
    session: DB, caller: Annotated[Caller, Depends(automation_or("audit"))]
) -> dict[str, Any]:
    """Row counts for the caller's scope, plus whether the audit chain is intact."""
    # Recompute the hash chain.
    ok, events = audit.verify(session)
    # Automation sees everything; a person sees their firm.
    tenant_id = caller.user.tenant_id if caller.user else None
    # Counts, chain status and number of events.
    return {
        "counts": reviews.counts(session, tenant_id),
        "audit_chain_ok": ok,
        "audit_events": events,
    }


# POST /v1/clients/{id}/reviews/run: run the multi-agent review.
@router.post("/clients/{client_ref}/reviews/run")
# Runs the LangGraph pipeline and stores the result.
def run_review(
    client_ref: str,
    body: RunIn,
    tasks: BackgroundTasks,
    session: DB,
    caller: Annotated[Caller, Depends(automation_or("approve"))],
) -> dict[str, Any]:
    """Run the multi-agent review once and store it for each firm in scope that has the client."""
    # (firm, client) pairs in scope that have this client.
    targets = [
        (firm, client)
        for firm in _firms(session, caller)
        if (client := get_client(session, firm, client_ref)) is not None
    ]
    # Nothing to review.
    if not targets:
        # Unknown client.
        raise HTTPException(404, "client not found: run the pipeline sync first")
    # The shared review pipeline (Groq/Gemini or firm policy).
    pipeline = get_pipeline()  # LangGraph graph with Groq/Gemini (or firm policy)
    # Time the run.
    t0 = time.perf_counter()
    # The agents run once…
    state = pipeline.run(client_ref, body.profile)  # the agents run once…
    # Elapsed milliseconds.
    latency = round((time.perf_counter() - t0) * 1000)
    # Which model (or "policy") produced it.
    model = pipeline.llm.name if pipeline.llm else "policy"
    # …and the result is stored for each firm in scope (same synthetic book, same findings).
    runs = [  # …and the result is recorded per firm (same synthetic book, same findings)
        reviews.record_run(
            session, firm, client, state, model=model, trigger=body.trigger, latency_ms=latency
        )
        for firm, client in targets
    ]
    # Tell n8n about each run after the response is sent.
    for run in runs:  # tell n8n after the response is sent (IDs and counts only)
        # Background task: IDs and counts only, never text or names.
        tasks.add_task(
            get_sink().emit,
            "review.drafted",
            {"client": client_ref, "run_id": run.id, "kept": run.kept, "dropped": run.dropped},
        )
    # The run returned to the caller.
    first = runs[0]
    # Run id, model, counts, timing and the findings with their status.
    return {
        "run_id": first.id,
        "runs": len(runs),
        "client": client_ref,
        "model": model,
        "kept": first.kept,
        "dropped": first.dropped,
        "latency_ms": latency,
        "findings": [
            {"id": f.id, "ref": f.ref, "kind": f.kind, "severity": f.severity, "status": f.status}
            for f in first.findings
        ],
    }


# GET /v1/reviews/pending: reviews waiting for an adviser.
@router.get("/reviews/pending")
# Clients whose latest run has open drafts.
def pending_reviews(
    session: DB, caller: Annotated[Caller, Depends(automation_or("approve"))]
) -> list[dict[str, Any]]:
    """Clients whose latest review is waiting for an advisor."""
    # One entry per waiting client across the firms in scope.
    return [asdict(p) for firm in _firms(session, caller) for p in reviews.pending(session, firm)]


# POST /v1/findings/{id}/decision: accept, dismiss or snooze.
@router.post("/findings/{finding_id}/decision")
# Only roles that can approve.
def decide(
    finding_id: str,
    body: DecisionIn,
    session: DB,
    user: Annotated[User, Depends(needs("approve"))],
) -> dict[str, str]:
    """Accept, dismiss or snooze one finding (advisers and owners only)."""
    # Look the finding up.
    finding = session.get(Finding, finding_id)
    # Other firms' findings look like they do not exist.
    if finding is None or finding.tenant_id != user.tenant_id:  # other firms' rows: not found
        # Not found.
        raise HTTPException(404, "finding not found")
    # Business-rule errors become HTTP 409.
    try:
        # Record it; the approver comes from the sign-in token, not the request body.
        reviews.decide(session, finding, body.decision, user.id)
    # Unknown decision, or a finding a guard blocked.
    except ValueError as exc:
        # Conflict.
        raise HTTPException(409, str(exc)) from exc
    # The finding's new status.
    return {"id": finding.id, "status": finding.status}


# POST /v1/clients/{id}/reviews/approve: the human approval step.
@router.post("/clients/{client_ref}/reviews/approve")
# Only signed-in roles with the approve capability.
def approve(
    client_ref: str,
    body: ApproveIn,
    tasks: BackgroundTasks,
    session: DB,
    user: Annotated[User, Depends(needs("approve"))],
) -> dict[str, Any]:
    """Approve a client's review with the advisor's decisions; the approver comes from the token."""
    # The client must belong to the approver's firm.
    firm, client = _own_client(session, user, client_ref)
    # Store the approval, apply decisions, extend the audit chain.
    review = reviews.approve(session, firm, client, body.decisions, user.id, "console")
    # Tell n8n after responding (IDs only).
    tasks.add_task(
        get_sink().emit,
        "review.approved",
        {"client": client_ref, "review_id": review.id, "run_id": review.run_id},
    )
    # Approval id and status.
    return {"review_id": review.id, "run_id": review.run_id, "status": review.status}


# GET /v1/audit/verify: is the audit chain intact?
@router.get("/audit/verify")
# Open to automation and to roles that may read the audit.
def audit_verify(
    session: DB, caller: Annotated[Caller, Depends(automation_or("audit"))]
) -> dict[str, Any]:
    """Recompute the hash chain; any edited, deleted or reordered entry makes it fail."""
    # Recompute every hash.
    ok, events = audit.verify(session)
    # Intact or not, and how many entries.
    return {"ok": ok, "events": events}
