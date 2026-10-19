from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aicfo.agents.review import serialise
from aicfo.agents.service import get_copilot, get_pipeline
from aicfo.core.analytics import snapshot
from aicfo.core.book import load_book

router = APIRouter(prefix="/v1", tags=["agents"])


class ClientOut(BaseModel):
    id: str
    risk: str
    total: int
    equity_pct: float


class ReviewIn(BaseModel):
    profile: Literal["RIA", "MFD"] = "RIA"
    dismissed: list[str] = Field(default_factory=list)


class CopilotIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.get("/clients", response_model=list[ClientOut])
def clients() -> list[ClientOut]:
    """Pseudonymous list: names live only in the advisor's browser vault in production."""
    book = load_book()
    out = []
    for cid in book.clients:
        s = snapshot(cid, book)
        out.append(
            ClientOut(
                id=cid,
                risk=s.client.risk,
                total=round(s.total),
                equity_pct=round(s.allocation_pct["Equity"], 2),
            )
        )
    return out


@router.post("/clients/{client_id}/review")
def review(client_id: str, body: ReviewIn) -> dict[str, Any]:
    if client_id not in load_book().clients:
        raise HTTPException(404, "client not found")
    return serialise(get_pipeline().run(client_id, body.profile, body.dismissed))


@router.post("/clients/{client_id}/copilot")
def copilot(client_id: str, body: CopilotIn) -> dict[str, Any]:
    if client_id not in load_book().clients:
        raise HTTPException(404, "client not found")
    a = get_copilot().ask(client_id, body.question)
    return {
        "question": a.question,
        "answer": a.answer,
        "mode": a.mode,
        "tool_calls": a.tool_calls,
        "citations": a.citations,
        "issues": a.issues,
    }
