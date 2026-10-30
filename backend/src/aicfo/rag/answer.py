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
from aicfo.rag.text import normalise_citations, numbers, sentences, tokenize
from aicfo.security.redaction import redact

# The instruction given to the model: answer ONLY from the numbered passages, cite them, say NOT_FOUND otherwise.
SYSTEM_PROMPT = """You answer questions for SEBI-registered advisers using ONLY the numbered context passages.
Rules:
- Cite every claim with the passage number in square brackets, e.g. [1] or [2][3].
- Use only facts and numbers that appear in the passages. Do not add outside knowledge.
- If the passages do not answer the question, reply exactly: NOT_FOUND
- Never tell anyone to buy, sell or hold a specific security, and never promise returns.
- Answer in at most 4 short sentences."""

# Matches a citation marker like [1].
_CITATION = re.compile(r"\[(\d+)\]")
# The honest reply when the rulebook does not cover the question.
NOT_FOUND = (
    "The knowledge base does not cover this question. Try rephrasing, or check the primary source."
)


@dataclass(frozen=True)
# A cited passage with enough detail to show and link its source.
class Citation:
    # The marker number used in the text, e.g. 1 for [1].
    n: int
    # Passage id.
    chunk_id: str
    # Source document id.
    doc_id: str
    # Document title.
    title: str
    # Who published it (SEBI, CBDT, AMFI, the firm).
    issuer: str
    # Heading the passage came from.
    section: str
    # Official link.
    source_url: str
    # Document version or date, for reproducibility.
    version: str
    # The passage text.
    excerpt: str


@dataclass
# A finished answer.
class Answer:
    # The (redacted) question.
    question: str
    # The answer text, with [n] citations.
    text: str
    # llm = model answer that passed the verifier; extractive = quoted sentences; refused = advice request; not_found = not covered.
    mode: Literal["llm", "extractive", "refused", "not_found"]
    # Passages cited.
    citations: list[Citation] = field(default_factory=list)
    # Everything retrieved (shown in the console).
    hits: list[Hit] = field(default_factory=list)
    # Why a model answer was rejected, if it was.
    issues: list[str] = field(default_factory=list)


# Build a Citation from a search hit.
def _citation(n: int, hit: Hit) -> Citation:
    # The passage.
    c = hit.chunk
    # Copy its fields.
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


# Check a model's answer against what was retrieved. Empty list = passed.
def verify(text: str, hits: list[Hit], question: str = "") -> list[str]:
    """Return problems with a generated answer (empty list means it passed)."""
    # Problems found.
    issues: list[str] = []
    # Which [n] markers the answer uses.
    cited = {int(n) for n in _CITATION.findall(text)}
    # Every claim must cite something.
    if not cited:
        # Record it.
        issues.append("no citations")
    # A marker that points at a passage that was not retrieved.
    if bad := sorted(n for n in cited if n < 1 or n > len(hits)):
        issues.append(f"citations out of range: {bad}")
    # Numbers the answer may contain: those in the retrieved passages or in the question.
    allowed = (
        set().union(*(numbers(h.chunk.text) for h in hits), numbers(question))
        if hits
        else numbers(question)
    )
    # Numbers in the answer (markers removed) that no source supports.
    unsupported = sorted(n for n in numbers(_CITATION.sub("", text)) if n not in allowed)
    # An invented number is rejected.
    if unsupported:
        issues.append(f"numbers not in sources: {unsupported}")
    # Finally the wording rules (no advice, no promises).
    guard = check_answer(text)
    # Blocked wording.
    if not guard.allowed:
        issues.append(f"compliance: {guard.reason}")
    # Empty if the answer is safe to show.
    return issues


# Fallback with no model: quote the best-matching sentences, each with its citation.
def extractive_answer(
    question: str, hits: list[Hit], max_sentences: int = 3
) -> tuple[str, list[int]]:
    """Quote the sentences that best match the question, each with its citation.

    A sentence must share at least half as many question terms as the best
    sentence, so loosely related passages are not padded into the answer.
    """
    # The question's words (stemmed, stop words removed).
    q = set(tokenize(question))
    # Candidate sentences with their match score.
    scored: list[tuple[float, int, int, str]] = []
    # Each retrieved passage, best first.
    for n, hit in enumerate(hits, 1):
        # Each sentence in it.
        for pos, s in enumerate(sentences(hit.chunk.text)):
            # How many question words the sentence shares.
            overlap = len(q & set(tokenize(s)))
            # Ignore sentences with no shared words.
            if overlap:
                # Score = shared words, with a small bonus for earlier passages and sentences.
                scored.append((overlap + 0.5 / n - 0.01 * pos, overlap, n, s))
    # Nothing matched.
    if not scored:
        # No answer.
        return "", []
    # The best sentence's match count.
    best = max(o for _, o, _, _ in scored)
    # A sentence must match at least ~60% as many words as the best one.
    floor = 1 if best == 1 else max(2, math.ceil(0.6 * best))
    # Drop weaker sentences so loosely related text is not padded in.
    scored = [x for x in scored if x[1] >= floor]
    # Best first.
    scored.sort(key=lambda x: -x[0])
    # Chosen sentences as (passage number, text).
    picked: list[tuple[int, str]] = []
    # Take them in order…
    for _, _, n, s in scored:
        # …skipping duplicates…
        if s not in (p[1] for p in picked):
            # …and keep each.
            picked.append((n, s))
        # Stop at the maximum.
        if len(picked) == max_sentences:
            # Done.
            break
    # Sentences each followed by its [n], plus the passages used.
    return " ".join(f"{s} [{n}]" for n, s in picked), sorted({n for n, _ in picked})


# Answers a question from the rulebook, safely: guard → retrieve → gate → generate → verify → fall back.
class Answerer:
    # Configure the answerer.
    def __init__(
        self,
        retriever: HybridRetriever,
        llm: LLMProvider | None = None,
        k: int = 4,
        min_coverage: float = 0.4,
    ) -> None:
        # Hybrid search over the rulebook.
        self.retriever = retriever
        # Groq/Gemini, or None for extractive answers.
        self.llm = llm
        # How many passages to retrieve.
        self.k = k
        # Relevance gate: the top passage must contain at least this share of the question's information.
        self.min_coverage = min_coverage

    # How much of the question's information the top passage covers (0 to 1).
    def coverage(self, question: str, hit: Hit) -> float:
        """Share of the question's information (IDF-weighted terms) present in the top passage.

        Terms never seen in the corpus get the highest IDF, so an off-topic word
        such as a country name pulls coverage down and the question is declined.
        """
        # Word rarity: a rare word carries more information than a common one.
        idf = self.retriever.bm25.idf
        # Words the rulebook has never seen get the highest weight, so off-topic questions score low.
        unseen = max(idf.values(), default=1.0)
        # The question's distinct words.
        terms = set(tokenize(question))
        # Nothing to judge.
        if not terms:
            # Zero coverage.
            return 0.0
        # Words that appear in the passage.
        present = set(tokenize(hit.chunk.index_text))
        # Total information in the question.
        total = sum(idf.get(t, unseen) for t in terms)
        # Information covered by the passage ÷ total.
        return sum(idf.get(t, unseen) for t in terms if t in present) / total

    # Answer one question.
    def ask(self, question: str) -> Answer:
        # Mask PAN, phone, email and tokens first: identifiers never reach retrieval or a model.
        question = redact(question.strip())  # never send identifiers to retrieval or a model
        # Refuse requests for buy/sell calls.
        guard = check_question(question)
        # Explain politely, citing the rule on adviser responsibility.
        if not guard.allowed:
            # Find the passage about the adviser's suitability duty to cite.
            hits = self.retriever.search("investment adviser suitability rationale for advice", k=1)
            # A refusal with a citation.
            return Answer(
                question,
                "This assistant explains rules and computed facts; it does not recommend buying or selling a specific security. "
                "That decision rests with the registered adviser, recorded with the client's risk profile and the rationale [1].",
                "refused",
                [_citation(1, h) for h in hits],
                hits,
                [f"blocked: {guard.reason}"],
            )

        # Retrieve the best passages for the question.
        hits = self.retriever.search(question, k=self.k)
        # Relevance gate: if even the best passages barely cover the question, say it isn't covered.
        if not hits or max(self.coverage(question, h) for h in hits[:3]) < self.min_coverage:
            # Honest "not found" instead of a made-up answer.
            return Answer(question, NOT_FOUND, "not_found", [], hits)

        # Reasons a model answer might be rejected.
        issues: list[str] = []
        # Model available: try a generated answer first.
        if self.llm is not None:
            # Number the passages [1], [2]… so the model can cite them.
            context = "\n\n".join(
                f"[{n}] ({h.chunk.doc.title} — {h.chunk.section})\n{h.chunk.text}"
                for n, h in enumerate(hits, 1)
            )
            # Model failure must not break the feature.
            try:
                # Ask the model; convert 【1】-style brackets to [1].
                text = normalise_citations(  # 【1】 → [1] so the verifier can read citations
                    self.llm.complete(SYSTEM_PROMPT, f"Context:\n{context}\n\nQuestion: {question}")
                )
                # The model says the passages don't answer it.
                if text.strip() == "NOT_FOUND":
                    # Report not found.
                    return Answer(question, NOT_FOUND, "not_found", [], hits)
                # Check citations, numbers and wording against what was retrieved.
                issues = verify(text, hits, question)
                # Passed: use the model's answer.
                if not issues:
                    # Which passages it cited.
                    used = sorted({int(n) for n in _CITATION.findall(text)})
                    return Answer(
                        question, text, "llm", [_citation(n, hits[n - 1]) for n in used], hits
                    )
            # Provider error (rate limit, outage)…
            except LLMError as exc:
                # …is recorded, then we fall back.
                issues = [str(exc)]

        # Fallback: quote the best sentences from the passages, each cited.
        text, used = extractive_answer(question, hits)
        # Even the fallback found nothing.
        if not text:
            # Not found.
            return Answer(question, NOT_FOUND, "not_found", [], hits, issues)
        return Answer(
            question, text, "extractive", [_citation(n, hits[n - 1]) for n in used], hits, issues
        )
