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

# Search mode: both rankings fused (default), keywords only, or meaning only.
Mode = Literal["hybrid", "bm25", "dense"]


# One search result with its score and where it ranked in each method.
@dataclass(frozen=True)
class Hit:
    # The passage (a slice of a source document).
    chunk: Chunk
    # Fused RRF score; higher is better.
    score: float
    # Position in the keyword ranking (None if absent).
    bm25_rank: int | None
    # Position in the meaning ranking (None if absent).
    dense_rank: int | None
    # Raw keyword score.
    bm25_score: float
    # Raw cosine similarity.
    dense_score: float


# Searches the rulebook two ways (keywords and meaning) and merges the rankings.
class HybridRetriever:
    # Index the passages once, at start-up.
    def __init__(
        self, chunks: Sequence[Chunk], embedder: Embedder, rrf_k: int = 60, candidates: int = 20
    ) -> None:
        # An empty corpus cannot be searched.
        if not chunks:
            raise ValueError("retriever needs at least one chunk")
        # The passages.
        self.chunks = list(chunks)
        # Turns text into meaning vectors (bge-small, or a hashing fallback).
        self.embedder = embedder
        # RRF damping constant; 60 is the standard value.
        self.rrf_k = rrf_k
        # How many results each method contributes before fusion.
        self.candidates = candidates
        # Keyword index over the stemmed words of each passage.
        self.bm25 = BM25([tokenize(c.index_text) for c in self.chunks])
        # One meaning vector per passage.
        self.vectors = embedder.embed_documents([c.index_text for c in self.chunks])

    # Keyword ranking: best-matching passages for the query.
    def _bm25(self, query: str) -> list[tuple[int, float]]:
        # BM25 score of every passage.
        scores = self.bm25.scores(tokenize(query))
        # Keep passages that matched at least one word, best first.
        ranked = sorted(((i, s) for i, s in enumerate(scores) if s > 0), key=lambda x: -x[1])
        # Top candidates as (passage index, score).
        return ranked[: self.candidates]

    # Meaning ranking: passages whose vectors point the same way as the query's.
    def _dense(self, query: str) -> list[tuple[int, float]]:
        # Cosine similarity with every passage (vectors are normalised, so a dot product).
        sims = (self.vectors @ self.embedder.embed_query(query)[0]).tolist()
        # Indices from most to least similar.
        order = np.argsort(-np.asarray(sims))[: self.candidates]
        # Top candidates as (passage index, similarity).
        return [(int(i), float(sims[int(i)])) for i in order]

    # Return the top `k` passages for a query.
    def search(self, query: str, k: int = 5, mode: Mode = "hybrid") -> list[Hit]:
        # Keyword ranking (skipped in dense-only mode).
        lexical = self._bm25(query) if mode in ("hybrid", "bm25") else []
        # Meaning ranking (skipped in keyword-only mode).
        dense = self._dense(query) if mode in ("hybrid", "dense") else []
        # Passage → rank in the keyword list (1 = best).
        b_rank = {i: r for r, (i, _) in enumerate(lexical, 1)}
        # Passage → rank in the meaning list.
        d_rank = {i: r for r, (i, _) in enumerate(dense, 1)}
        # Passage → raw keyword score.
        b_score = dict(lexical)
        # Passage → raw similarity.
        d_score = dict(dense)
        # Reciprocal Rank Fusion scores.
        fused: dict[int, float] = {}
        # Each ranking votes for its passages…
        for ranks in (b_rank, d_rank):
            # …with weight 1/(k+rank), so high ranks count most and no score calibration is needed.
            for i, r in ranks.items():
                # Add this ranking's vote.
                fused[i] = fused.get(i, 0.0) + 1.0 / (self.rrf_k + r)
        # Best fused score first, cut to k.
        order = sorted(fused, key=lambda i: -fused[i])[:k]
        # Package each result with its ranks and scores (shown in the console).
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
