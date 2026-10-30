from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aicfo.agents.review import serialise
from aicfo.agents.service import get_copilot, get_pipeline
from aicfo.core.analytics import snapshot
from aicfo.core.book import load_book

# All routes live under /v1.
router = APIRouter(prefix="/v1", tags=["agents"])


# A client in the list, pseudonymous (no name).
class ClientOut(BaseModel):
    # Pseudonymous client id.
    id: str
    # Risk profile.
    risk: str
    # Portfolio value in rupees.
    total: int
    # Share in equity.
    equity_pct: float


# Body of "run a review".
class ReviewIn(BaseModel):
    # RIA or MFD wording rules.
    profile: Literal["RIA", "MFD"] = "RIA"
    # Finding ids the adviser dismissed before.
    dismissed: list[str] = Field(default_factory=list)


# Body of "ask the Copilot".
class CopilotIn(BaseModel):
    # 3 to 500 characters.
    question: str = Field(min_length=3, max_length=500)


# GET /v1/clients: the list the weekly n8n sweep walks through.
@router.get("/clients", response_model=list[ClientOut])
# Names live only in the adviser's browser; this list is pseudonymous.
def clients() -> list[ClientOut]:
    """Pseudonymous list: names live only in the advisor's browser vault in production."""
    # The synthetic book.
    book = load_book()
    # Rows to return.
    out = []
    # Each client.
    for cid in book.clients:
        # Compute their numbers.
        s = snapshot(cid, book)
        # Id, risk, value and equity share.
        out.append(
            ClientOut(
                id=cid,
                risk=s.client.risk,
                total=round(s.total),
                equity_pct=round(s.allocation_pct["Equity"], 2),
            )
        )
    # The list.
    return out


# POST /v1/clients/{id}/review: run the agents without storing anything.
@router.post("/clients/{client_id}/review")
# Used by the console's Agents page.
def review(client_id: str, body: ReviewIn) -> dict[str, Any]:
    # Unknown client.
    if client_id not in load_book().clients:
        # Not found.
        raise HTTPException(404, "client not found")
    # Run the LangGraph pipeline and return drafts, evidence and the trace.
    return serialise(get_pipeline().run(client_id, body.profile, body.dismissed))


# POST /v1/clients/{id}/copilot: ask the tool-using Copilot.
@router.post("/clients/{client_id}/copilot")
# Answers from tools and the rulebook.
def copilot(client_id: str, body: CopilotIn) -> dict[str, Any]:
    # Unknown client.
    if client_id not in load_book().clients:
        # Not found.
        raise HTTPException(404, "client not found")
    # Ask the Copilot.
    a = get_copilot().ask(client_id, body.question)
    # Answer, how it was produced, tool calls, citations and any issues.
    return {
        "question": a.question,
        "answer": a.answer,
        "mode": a.mode,
        "tool_calls": a.tool_calls,
        "citations": a.citations,
        "issues": a.issues,
    }
