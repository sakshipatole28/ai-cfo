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

GOLDEN = REPO_ROOT / "data" / "evals" / "rag_golden.json"


@dataclass(frozen=True)
class RetrievalReport:
    mode: str
    questions: int
    hit_at_1: float
    hit_at_3: float
    hit_at_5: float
    mrr: float


def load_golden(path: Path = GOLDEN) -> list[dict[str, object]]:
    data: list[dict[str, object]] = json.loads(path.read_text(encoding="utf-8"))
    return data


def evaluate(
    retriever: HybridRetriever, mode: Mode = "hybrid", golden: list[dict[str, object]] | None = None
) -> RetrievalReport:
    rows = golden or load_golden()
    hits = {1: 0, 3: 0, 5: 0}
    rr = 0.0
    for row in rows:
        expected = {str(d) for d in row["docs"]}  # type: ignore[attr-defined]
        ranked = [h.chunk.doc.id for h in retriever.search(str(row["q"]), k=5, mode=mode)]
        first = next((i for i, d in enumerate(ranked, 1) if d in expected), None)
        if first:
            rr += 1 / first
            for k in hits:
                if first <= k:
                    hits[k] += 1
    n = len(rows)
    return RetrievalReport(mode, n, hits[1] / n, hits[3] / n, hits[5] / n, rr / n)
