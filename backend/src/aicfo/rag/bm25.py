"""Okapi BM25 lexical ranking (no external dependency)."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


class BM25:
    def __init__(self, docs: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = [len(d) for d in docs]
        self.avgdl = sum(self.len) / max(len(docs), 1)
        df: Counter[str] = Counter()
        for counts in self.tf:
            df.update(counts.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: Sequence[str]) -> list[float]:
        out = []
        for counts, length in zip(self.tf, self.len, strict=True):
            s = 0.0
            for term in set(query):
                f = counts.get(term)
                if not f:
                    continue
                norm = self.k1 * (1 - self.b + self.b * length / self.avgdl)
                s += self.idf[term] * f * (self.k1 + 1) / (f + norm)
            out.append(s)
        return out
