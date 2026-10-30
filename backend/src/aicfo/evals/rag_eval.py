"""Retrieval evaluation on the golden question set (data/evals/rag_golden.json).

Metrics are document-level: a question counts as a hit@k if any of its
expected documents appears among the top k retrieved chunks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aicfo.config import REPO_ROOT
from aicfo.rag.retriever import HybridRetriever, Mode

# The plain golden question set.
GOLDEN = REPO_ROOT / "data" / "evals" / "rag_golden.json"
# Paraphrased questions that avoid the documents' own wording, so keyword search alone struggles.
HARD = REPO_ROOT / "data" / "evals" / "rag_hard.json"


# Scores for one search mode.
@dataclass(frozen=True)
class RetrievalReport:
    # hybrid, bm25 or dense.
    mode: str
    # How many questions.
    questions: int
    # Share where the right document is first.
    hit_at_1: float
    # Share where it is in the top 3.
    hit_at_3: float
    # Share where it is in the top 5.
    hit_at_5: float
    # Mean reciprocal rank (1 = always first).
    mrr: float


# Read a question set (JSON list of {q, docs}).
def load_golden(path: Path = GOLDEN) -> list[dict[str, object]]:
    # Parsed JSON.
    data: list[dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
    # The questions.
    return data


# Score a retriever on a question set.
def evaluate(
    retriever: HybridRetriever, mode: Mode = "hybrid", golden: list[dict[str, object]] | None = None
) -> RetrievalReport:
    # Questions to ask.
    rows = golden or load_golden()
    # Counts of questions answered within the top 1, 3 and 5.
    hits = {1: 0, 3: 0, 5: 0}
    # Sum of reciprocal ranks.
    rr = 0.0
    # Each question.
    for row in rows:
        # Documents that count as correct.
        expected = {str(d) for d in row["docs"]}  # type: ignore[attr-defined]
        # Documents returned, in order.
        ranked = [h.chunk.doc.id for h in retriever.search(str(row["q"]), k=5, mode=mode)]
        # Position of the first correct document.
        first = next((i for i, d in enumerate(ranked, 1) if d in expected), None)
        # Found within the top 5.
        if first:
            # 1 for first place, ½ for second…
            rr += 1 / first
            # Each cutoff.
            for k in hits:
                # Found within the top k.
                if first <= k:
                    # Count it.
                    hits[k] += 1
    # Number of questions.
    n = len(rows)
    # Shares and mean reciprocal rank.
    return RetrievalReport(mode, n, hits[1] / n, hits[3] / n, hits[5] / n, rr / n)
