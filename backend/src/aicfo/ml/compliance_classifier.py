"""Advice-likelihood classifier: the ML layer of the compliance guard.

Rules catch obvious cases; this model scores softer wording ("put your bonus
into ...") between the rules and the LLM judge. It is L2-regularised logistic
regression on hashed word and word-pair features, trained with numpy on the
labelled set in data/ml/compliance_sentences.jsonl (synthetic, 80 sentences).
Small and explainable on purpose: we can list the features behind each score.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from aicfo.config import REPO_ROOT
from aicfo.rag.text import _stem

_WORD = re.compile(r"[a-z₹]+")
IMPERATIVES = frozenset(
    [
        "buy",
        "sell",
        "exit",
        "invest",
        "switch",
        "add",
        "move",
        "put",
        "redeem",
        "stop",
        "start",
        "increase",
        "purchase",
        "shift",
        "transfer",
        "dump",
        "book",
        "go",
        "pick",
    ]
)
SECOND_PERSON = frozenset(["you", "your", "yours"])
MODALS = frozenset(["should", "must", "will", "definitely", "sure", "guaranteed", "assured"])

DATA = REPO_ROOT / "data" / "ml" / "compliance_sentences.jsonl"
Vector = NDArray[np.float64]


def load_dataset(path: Path = DATA) -> tuple[list[str], NDArray[np.int64]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return [r["text"] for r in rows], np.array([int(r["label"]) for r in rows], dtype=np.int64)


@dataclass(frozen=True)
class Metrics:
    accuracy: float
    precision: float
    recall: float
    f1: float


def metrics(y_true: NDArray[np.int64], y_pred: NDArray[np.int64]) -> Metrics:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return Metrics(float((y_true == y_pred).mean()), precision, recall, f1)


def features(text: str) -> list[str]:
    """Stemmed words and word pairs (stop words kept: "you should" matters here) plus cue flags."""
    words = [_stem(w) for w in _WORD.findall(text.lower())]
    feats = words + [f"{a}_{b}" for a, b in itertools.pairwise(words)]
    if words and words[0] in IMPERATIVES:
        feats.append("CUE:imperative_start")
    if SECOND_PERSON & set(words):
        feats.append("CUE:second_person")
    if MODALS & set(words):
        feats.append("CUE:modal")
    if any(ch.isdigit() for ch in text) and not (SECOND_PERSON & set(words)):
        feats.append("CUE:numeric_statement")
    return feats


class AdviceClassifier:
    def __init__(
        self, dim: int = 4096, l2: float = 1e-3, lr: float = 0.8, epochs: int = 500
    ) -> None:
        self.dim = dim
        self.l2, self.lr, self.epochs = l2, lr, epochs
        self.w: Vector = np.zeros(dim)
        self.b = 0.0

    def _x(self, texts: list[str]) -> Vector:
        x = np.zeros((len(texts), self.dim))
        for i, t in enumerate(texts):
            for f in features(t):
                h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
                x[i, h % self.dim] += 1.0
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        return x / np.where(norms == 0, 1.0, norms)

    def fit(self, texts: list[str], y: NDArray[np.int64]) -> AdviceClassifier:
        x = self._x(texts)
        n = len(texts)
        for _ in range(self.epochs):
            p = 1 / (1 + np.exp(-(x @ self.w + self.b)))
            grad = p - y
            self.w -= self.lr * (x.T @ grad / n + self.l2 * self.w)
            self.b -= self.lr * float(grad.mean())
        return self

    def predict_proba(self, texts: list[str]) -> Vector:
        return 1 / (1 + np.exp(-(self._x(texts) @ self.w + self.b)))

    def score(self, text: str) -> float:
        return float(self.predict_proba([text])[0])


def cross_validate(folds: int = 5, seed: int = 7) -> Metrics:
    """Stratified k-fold estimate of out-of-sample quality."""
    texts, y = load_dataset()
    rng = np.random.default_rng(seed)
    pos, neg = rng.permutation(np.where(y == 1)[0]), rng.permutation(np.where(y == 0)[0])
    preds = np.zeros_like(y)
    for k in range(folds):
        test = np.concatenate([pos[k::folds], neg[k::folds]])
        train = np.setdiff1d(np.arange(len(y)), test)
        model = AdviceClassifier().fit([texts[i] for i in train], y[train])
        preds[test] = (model.predict_proba([texts[i] for i in test]) >= 0.5).astype(np.int64)
    return metrics(y, preds)


@lru_cache
def get_classifier() -> AdviceClassifier:
    texts, y = load_dataset()
    return AdviceClassifier().fit(texts, y)
