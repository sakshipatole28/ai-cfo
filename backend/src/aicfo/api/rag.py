from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aicfo.rag.answer import Answer
from aicfo.rag.retriever import Hit
from aicfo.rag.service import get_rag

# Rulebook routes under /v1.
router = APIRouter(prefix="/v1", tags=["knowledge"])


# A source document in the knowledge base.
class DocumentOut(BaseModel):
    id: str
    issuer: str
    title: str
    source_url: str
    version: str
    effective: str
    kind: str
    chunks: int


# One retrieved passage with its scores.
class HitOut(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    score: float
    bm25_rank: int | None
    dense_rank: int | None


# Body of a search.
class SearchIn(BaseModel):
    # 3 to 500 characters.
    query: str = Field(min_length=3, max_length=500)
    # How many passages to return.
    k: int = Field(5, ge=1, le=20)
    # hybrid, bm25 or dense.
    mode: Literal["hybrid", "bm25", "dense"] = "hybrid"


# Body of a question.
class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


# A cited passage.
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


# A finished answer.
class AnswerOut(BaseModel):
    question: str
    answer: str
    mode: str
    citations: list[CitationOut]
    retrieved: list[HitOut]
    issues: list[str]


# Convert a search hit into the response shape.
def _hit(h: Hit) -> HitOut:
    # The passage.
    c = h.chunk
    # Copy its fields, rounding the score.
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


# GET /v1/kb/documents: what the knowledge base contains.
@router.get("/kb/documents", response_model=list[DocumentOut])
# Documents with their passage counts.
def list_documents() -> list[DocumentOut]:
    # The shared RAG service.
    rag = get_rag()
    # Passages per document.
    counts: dict[str, int] = {}
    # Count each passage.
    for c in rag.chunks:
        # Add one.
        counts[c.doc.id] = counts.get(c.doc.id, 0) + 1
    # One entry per document.
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


# POST /v1/rag/search: hybrid search only (no answer).
@router.post("/rag/search", response_model=list[HitOut])
# Return the top passages.
def search(body: SearchIn) -> list[HitOut]:
    # Passages with their BM25 and meaning scores.
    return [_hit(h) for h in get_rag().retriever.search(body.query, k=body.k, mode=body.mode)]


# POST /v1/rag/ask: a guarded, cited answer.
@router.post("/rag/ask", response_model=AnswerOut)
# Retrieve, answer, verify.
def ask(body: AskIn) -> AnswerOut:
    # Run the answerer (model if keys exist, else extractive).
    a: Answer = get_rag().answerer.ask(body.question)
    # Answer text, how it was made, its citations and what was retrieved.
    return AnswerOut(
        question=a.question,
        answer=a.text,
        mode=a.mode,
        citations=[CitationOut(**c.__dict__) for c in a.citations],
        retrieved=[_hit(h) for h in a.hits],
        issues=a.issues,
    )
