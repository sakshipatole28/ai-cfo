"""Hybrid retrieval: BM25 + dense vectors, merged with Reciprocal Rank Fusion.

RRF score = Σ 1 / (k + rank) over the rankings a chunk appears in. It needs no
score calibration between the two retrievers, which is why it is the default
fusion method for hybrid search.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from aicfo.rag.bm25 import BM25
from aicfo.rag.corpus import Chunk
from aicfo.rag.embeddings import Embedder
from aicfo.rag.text import tokenize

Mode = Literal["hybrid", "bm25", "dense"]


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    bm25_rank: int | None
    dense_rank: int | None
    bm25_score: float
    dense_score: float


class HybridRetriever:
    def __init__(
        self, chunks: Sequence[Chunk], embedder: Embedder, rrf_k: int = 60, candidates: int = 20
    ) -> None:
        if not chunks:
            raise ValueError("retriever needs at least one chunk")
        self.chunks = list(chunks)
        self.embedder = embedder
        self.rrf_k = rrf_k
        self.candidates = candidates
        self.bm25 = BM25([tokenize(c.index_text) for c in self.chunks])
        self.vectors = embedder.embed_documents([c.index_text for c in self.chunks])

    def _bm25(self, query: str) -> list[tuple[int, float]]:
        scores = self.bm25.scores(tokenize(query))
        ranked = sorted(((i, s) for i, s in enumerate(scores) if s > 0), key=lambda x: -x[1])
        return ranked[: self.candidates]

    def _dense(self, query: str) -> list[tuple[int, float]]:
        sims = (self.vectors @ self.embedder.embed_query(query)[0]).tolist()
        order = np.argsort(-np.asarray(sims))[: self.candidates]
        return [(int(i), float(sims[int(i)])) for i in order]

    def search(self, query: str, k: int = 5, mode: Mode = "hybrid") -> list[Hit]:
        lexical = self._bm25(query) if mode in ("hybrid", "bm25") else []
        dense = self._dense(query) if mode in ("hybrid", "dense") else []
        b_rank = {i: r for r, (i, _) in enumerate(lexical, 1)}
        d_rank = {i: r for r, (i, _) in enumerate(dense, 1)}
        b_score = dict(lexical)
        d_score = dict(dense)
        fused: dict[int, float] = {}
        for ranks in (b_rank, d_rank):
            for i, r in ranks.items():
                fused[i] = fused.get(i, 0.0) + 1.0 / (self.rrf_k + r)
        order = sorted(fused, key=lambda i: -fused[i])[:k]
        return [
            Hit(
                chunk=self.chunks[i],
                score=fused[i],
                bm25_rank=b_rank.get(i),
                dense_rank=d_rank.get(i),
                bm25_score=b_score.get(i, 0.0),
                dense_score=d_score.get(i, 0.0),
            )
            for i in order
        ]
