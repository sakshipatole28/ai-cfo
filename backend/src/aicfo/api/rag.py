from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aicfo.rag.answer import Answer
from aicfo.rag.retriever import Hit
from aicfo.rag.service import get_rag

router = APIRouter(prefix="/v1", tags=["knowledge"])


class DocumentOut(BaseModel):
    id: str
    issuer: str
    title: str
    source_url: str
    version: str
    effective: str
    kind: str
    chunks: int


class HitOut(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    score: float
    bm25_rank: int | None
    dense_rank: int | None


class SearchIn(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    k: int = Field(5, ge=1, le=20)
    mode: Literal["hybrid", "bm25", "dense"] = "hybrid"


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class CitationOut(BaseModel):
    n: int
    chunk_id: str
    doc_id: str
    title: str
    issuer: str
    section: str
    source_url: str
    version: str
    excerpt: str


class AnswerOut(BaseModel):
    question: str
    answer: str
    mode: str
    citations: list[CitationOut]
    retrieved: list[HitOut]
    issues: list[str]


def _hit(h: Hit) -> HitOut:
    c = h.chunk
    return HitOut(
        chunk_id=c.id,
        doc_id=c.doc.id,
        title=c.doc.title,
        section=c.section,
        text=c.text,
        score=round(h.score, 5),
        bm25_rank=h.bm25_rank,
        dense_rank=h.dense_rank,
    )


@router.get("/kb/documents", response_model=list[DocumentOut])
def list_documents() -> list[DocumentOut]:
    rag = get_rag()
    counts: dict[str, int] = {}
    for c in rag.chunks:
        counts[c.doc.id] = counts.get(c.doc.id, 0) + 1
    return [
        DocumentOut(
            id=d.id,
            issuer=d.issuer,
            title=d.title,
            source_url=d.source_url,
            version=d.version,
            effective=d.effective,
            kind=d.kind,
            chunks=counts.get(d.id, 0),
        )
        for d in rag.documents
    ]


@router.post("/rag/search", response_model=list[HitOut])
def search(body: SearchIn) -> list[HitOut]:
    return [_hit(h) for h in get_rag().retriever.search(body.query, k=body.k, mode=body.mode)]


@router.post("/rag/ask", response_model=AnswerOut)
def ask(body: AskIn) -> AnswerOut:
    a: Answer = get_rag().answerer.ask(body.question)
    return AnswerOut(
        question=a.question,
        answer=a.text,
        mode=a.mode,
        citations=[CitationOut(**c.__dict__) for c in a.citations],
        retrieved=[_hit(h) for h in a.hits],
        issues=a.issues,
    )
