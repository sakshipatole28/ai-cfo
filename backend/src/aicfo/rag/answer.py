"""Grounded answers with citations.

Pipeline: guard the question → retrieve → generate (LLM or extractive) → verify
→ guard the answer. The verifier rejects an LLM answer whose citations do not
point at retrieved passages or that contains numbers absent from those
passages; the service then falls back to an extractive answer built only from
quoted sentences.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Literal

from aicfo.llm import LLMError, LLMProvider
from aicfo.rag.guard import check_answer, check_question
from aicfo.rag.retriever import Hit, HybridRetriever
from aicfo.rag.text import numbers, sentences, tokenize
from aicfo.security.redaction import redact

SYSTEM_PROMPT = """You answer questions for SEBI-registered advisers using ONLY the numbered context passages.
Rules:
- Cite every claim with the passage number in square brackets, e.g. [1] or [2][3].
- Use only facts and numbers that appear in the passages. Do not add outside knowledge.
- If the passages do not answer the question, reply exactly: NOT_FOUND
- Never tell anyone to buy, sell or hold a specific security, and never promise returns.
- Answer in at most 4 short sentences."""

_CITATION = re.compile(r"\[(\d+)\]")
NOT_FOUND = (
    "The knowledge base does not cover this question. Try rephrasing, or check the primary source."
)


@dataclass(frozen=True)
class Citation:
    n: int
    chunk_id: str
    doc_id: str
    title: str
    issuer: str
    section: str
    source_url: str
    version: str
    excerpt: str


@dataclass
class Answer:
    question: str
    text: str
    mode: Literal["llm", "extractive", "refused", "not_found"]
    citations: list[Citation] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _citation(n: int, hit: Hit) -> Citation:
    c = hit.chunk
    return Citation(
        n,
        c.id,
        c.doc.id,
        c.doc.title,
        c.doc.issuer,
        c.section,
        c.doc.source_url,
        c.doc.version,
        c.text,
    )


def verify(text: str, hits: list[Hit], question: str = "") -> list[str]:
    """Return problems with a generated answer (empty list means it passed)."""
    issues: list[str] = []
    cited = {int(n) for n in _CITATION.findall(text)}
    if not cited:
        issues.append("no citations")
    if bad := sorted(n for n in cited if n < 1 or n > len(hits)):
        issues.append(f"citations out of range: {bad}")
    allowed = (
        set().union(*(numbers(h.chunk.text) for h in hits), numbers(question))
        if hits
        else numbers(question)
    )
    unsupported = sorted(n for n in numbers(_CITATION.sub("", text)) if n not in allowed)
    if unsupported:
        issues.append(f"numbers not in sources: {unsupported}")
    guard = check_answer(text)
    if not guard.allowed:
        issues.append(f"compliance: {guard.reason}")
    return issues


def extractive_answer(
    question: str, hits: list[Hit], max_sentences: int = 3
) -> tuple[str, list[int]]:
    """Quote the sentences that best match the question, each with its citation.

    A sentence must share at least half as many question terms as the best
    sentence, so loosely related passages are not padded into the answer.
    """
    q = set(tokenize(question))
    scored: list[tuple[float, int, int, str]] = []
    for n, hit in enumerate(hits, 1):
        for pos, s in enumerate(sentences(hit.chunk.text)):
            overlap = len(q & set(tokenize(s)))
            if overlap:
                scored.append((overlap + 0.5 / n - 0.01 * pos, overlap, n, s))
    if not scored:
        return "", []
    best = max(o for _, o, _, _ in scored)
    floor = 1 if best == 1 else max(2, math.ceil(0.6 * best))
    scored = [x for x in scored if x[1] >= floor]
    scored.sort(key=lambda x: -x[0])
    picked: list[tuple[int, str]] = []
    for _, _, n, s in scored:
        if s not in (p[1] for p in picked):
            picked.append((n, s))
        if len(picked) == max_sentences:
            break
    return " ".join(f"{s} [{n}]" for n, s in picked), sorted({n for n, _ in picked})


class Answerer:
    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMProvider | None = None,
        k: int = 4,
        min_coverage: float = 0.4,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.k = k
        self.min_coverage = min_coverage

    def coverage(self, question: str, hit: Hit) -> float:
        """Share of the question's information (IDF-weighted terms) present in the top passage.

        Terms never seen in the corpus get the highest IDF, so an off-topic word
        such as a country name pulls coverage down and the question is declined.
        """
        idf = self.retriever.bm25.idf
        unseen = max(idf.values(), default=1.0)
        terms = set(tokenize(question))
        if not terms:
            return 0.0
        present = set(tokenize(hit.chunk.index_text))
        total = sum(idf.get(t, unseen) for t in terms)
        return sum(idf.get(t, unseen) for t in terms if t in present) / total

    def ask(self, question: str) -> Answer:
        question = redact(question.strip())  # never send identifiers to retrieval or a model
        guard = check_question(question)
        if not guard.allowed:
            hits = self.retriever.search("investment adviser suitability rationale for advice", k=1)
            return Answer(
                question,
                "This assistant explains rules and computed facts; it does not recommend buying or selling a specific security. "
                "That decision rests with the registered adviser, recorded with the client's risk profile and the rationale [1].",
                "refused",
                [_citation(1, h) for h in hits],
                hits,
                [f"blocked: {guard.reason}"],
            )

        hits = self.retriever.search(question, k=self.k)
        if not hits or max(self.coverage(question, h) for h in hits[:3]) < self.min_coverage:
            return Answer(question, NOT_FOUND, "not_found", [], hits)

        issues: list[str] = []
        if self.llm is not None:
            context = "\n\n".join(
                f"[{n}] ({h.chunk.doc.title} — {h.chunk.section})\n{h.chunk.text}"
                for n, h in enumerate(hits, 1)
            )
            try:
                text = self.llm.complete(
                    SYSTEM_PROMPT, f"Context:\n{context}\n\nQuestion: {question}"
                )
                if text.strip() == "NOT_FOUND":
                    return Answer(question, NOT_FOUND, "not_found", [], hits)
                issues = verify(text, hits, question)
                if not issues:
                    used = sorted({int(n) for n in _CITATION.findall(text)})
                    return Answer(
                        question, text, "llm", [_citation(n, hits[n - 1]) for n in used], hits
                    )
            except LLMError as exc:
                issues = [str(exc)]

        text, used = extractive_answer(question, hits)
        if not text:
            return Answer(question, NOT_FOUND, "not_found", [], hits, issues)
        return Answer(
            question, text, "extractive", [_citation(n, hits[n - 1]) for n in used], hits, issues
        )
