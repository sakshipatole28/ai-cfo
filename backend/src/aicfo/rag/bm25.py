"""Okapi BM25 lexical ranking (no external dependency)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


# Okapi BM25: classic keyword ranking that rewards rare words and discounts long passages.
class BM25:
    # Pre-compute word counts and word rarity for every passage.
    def __init__(self, docs: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        # k1: how fast repeated words saturate; b: how strongly length is penalised.
        self.k1, self.b = k1, b
        # Word counts per passage (term frequency).
        self.tf = [Counter(d) for d in docs]
        # Passage lengths in words.
        self.len = [len(d) for d in docs]
        # Average passage length.
        self.avgdl = sum(self.len) / max(len(docs), 1)
        # In how many passages each word appears (document frequency).
        df: Counter[str] = Counter()
        # Count each word once per passage.
        for counts in self.tf:
            # Add this passage's distinct words.
            df.update(counts.keys())
        # Number of passages.
        n = len(docs)
        # Rarity of each word: rare words are worth more than common ones.
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    # BM25 score of every passage for a tokenised query.
    def scores(self, query: Sequence[str]) -> list[float]:
        # One score per passage.
        out = []
        # Each passage.
        for counts, length in zip(self.tf, self.len, strict=True):
            # Running score.
            s = 0.0
            # Each distinct query word.
            for term in set(query):
                # How often it appears in this passage.
                f = counts.get(term)
                # Absent words add nothing.
                if not f:
                    # Next word.
                    continue
                # Length normalisation: long passages are penalised.
                norm = self.k1 * (1 - self.b + self.b * length / self.avgdl)
                # Add this word's contribution: rarity × saturated frequency.
                s += self.idf[term] * f * (self.k1 + 1) / (f + norm)
            # Store the passage's score.
            out.append(s)
        # All scores.
        return out
