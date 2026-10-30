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

# A word: letters (and ₹).
_WORD = re.compile(r"[a-z₹]+")
# Verbs that start a command ("buy", "sell", "switch"…): a strong sign of advice.
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
# "you" words: advice is usually addressed to someone.
SECOND_PERSON = frozenset(["you", "your", "yours"])
# Strong words ("should", "definitely", "guaranteed"…).
MODALS = frozenset(["should", "must", "will", "definitely", "sure", "guaranteed", "assured"])

# The labelled training sentences (synthetic).
DATA = REPO_ROOT / "data" / "ml" / "compliance_sentences.jsonl"
# A 1-D array of floats.
Vector = NDArray[np.float64]


# Read the labelled sentences: text and label (1 = advice, 0 = information).
def load_dataset(path: Path = DATA) -> tuple[list[str], NDArray[np.int64]]:
    # One JSON object per line.
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    # Texts, and labels as an integer array.
    return [r["text"] for r in rows], np.array([int(r["label"]) for r in rows], dtype=np.int64)


# Quality scores of the classifier.
@dataclass(frozen=True)
class Metrics:
    # Share of all sentences classified right.
    accuracy: float
    # Of those flagged as advice, how many really were.
    precision: float
    # Of the real advice, how much was caught.
    recall: float
    # Balance of precision and recall.
    f1: float


# Compute the four scores from true and predicted labels.
def metrics(y_true: NDArray[np.int64], y_pred: NDArray[np.int64]) -> Metrics:
    # True positives: advice correctly flagged.
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    # False positives: information wrongly flagged.
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    # False negatives: advice that was missed.
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    # tp ÷ (tp + fp).
    precision = tp / (tp + fp) if tp + fp else 0.0
    # tp ÷ (tp + fn).
    recall = tp / (tp + fn) if tp + fn else 0.0
    # Harmonic mean of the two.
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    # Accuracy is the share of matching labels.
    return Metrics(float((y_true == y_pred).mean()), precision, recall, f1)


# Turn a sentence into features the model can weigh.
def features(text: str) -> list[str]:
    """Stemmed words and word pairs (stop words kept: "you should" matters here) plus cue flags."""
    # Stemmed words.
    words = [_stem(w) for w in _WORD.findall(text.lower())]
    # Words plus neighbouring pairs ("you should" matters).
    feats = words + [f"{a}_{b}" for a, b in itertools.pairwise(words)]
    # Starts with a command verb.
    if words and words[0] in IMPERATIVES:
        # Cue: imperative start.
        feats.append("CUE:imperative_start")
    # Addressed to "you".
    if SECOND_PERSON & set(words):
        # Cue: second person.
        feats.append("CUE:second_person")
    # Contains a strong modal word.
    if MODALS & set(words):
        # Cue: modal.
        feats.append("CUE:modal")
    # Has a number and is not addressed to "you": a statement of fact.
    if any(ch.isdigit() for ch in text) and not (SECOND_PERSON & set(words)):
        # Cue: numeric statement (leans towards information).
        feats.append("CUE:numeric_statement")
    # All features.
    return feats


# Logistic regression written in numpy: small, fast and explainable.
class AdviceClassifier:
    # Hyper-parameters: feature space size, regularisation strength, learning rate, passes.
    def __init__(
        self, dim: int = 4096, l2: float = 1e-3, lr: float = 0.8, epochs: int = 500
    ) -> None:
        # Number of hashed feature slots.
        self.dim = dim
        # Regularisation, learning rate, passes over the data.
        self.l2, self.lr, self.epochs = l2, lr, epochs
        # One weight per slot, learned in training.
        self.w: Vector = np.zeros(dim)
        # Bias term.
        self.b = 0.0

    # Turn texts into a matrix of hashed feature counts.
    def _x(self, texts: list[str]) -> Vector:
        # One row per text.
        x = np.zeros((len(texts), self.dim))
        # Each text.
        for i, t in enumerate(texts):
            # Each feature.
            for f in features(t):
                # Stable hash of the feature.
                h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
                # Count it in its hashed slot.
                x[i, h % self.dim] += 1.0
        # Row lengths.
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        # Scale rows to length 1 so long sentences do not dominate.
        return x / np.where(norms == 0, 1.0, norms)

    # Train by gradient descent.
    def fit(self, texts: list[str], y: NDArray[np.int64]) -> AdviceClassifier:
        # Feature matrix.
        x = self._x(texts)
        # Number of sentences.
        n = len(texts)
        # Repeat many passes.
        for _ in range(self.epochs):
            # Current predicted probability of advice (sigmoid).
            p = 1 / (1 + np.exp(-(x @ self.w + self.b)))
            # Error: predicted minus true.
            grad = p - y
            # Move the weights against the error gradient (plus L2 shrinkage).
            self.w -= self.lr * (x.T @ grad / n + self.l2 * self.w)
            # Move the bias.
            self.b -= self.lr * float(grad.mean())
        # The trained model.
        return self

    # Probability of advice for many texts.
    def predict_proba(self, texts: list[str]) -> Vector:
        # Sigmoid of the weighted sum.
        return 1 / (1 + np.exp(-(self._x(texts) @ self.w + self.b)))

    # Probability of advice for one text.
    def score(self, text: str) -> float:
        # Between 0 and 1.
        return float(self.predict_proba([text])[0])


# 5-fold cross-validation: train on 4/5, test on 1/5, five times, to estimate real-world quality.
def cross_validate(folds: int = 5, seed: int = 7) -> Metrics:
    """Stratified k-fold estimate of out-of-sample quality."""
    # Labelled data.
    texts, y = load_dataset()
    # Seeded random generator, so results are repeatable.
    rng = np.random.default_rng(seed)
    # Shuffled advice and information examples.
    pos, neg = rng.permutation(np.where(y == 1)[0]), rng.permutation(np.where(y == 0)[0])
    # Predictions for every sentence.
    preds = np.zeros_like(y)
    # Each fold.
    for k in range(folds):
        # This fold's test sentences (balanced across both classes).
        test = np.concatenate([pos[k::folds], neg[k::folds]])
        # Everything else.
        train = np.setdiff1d(np.arange(len(y)), test)
        # Train on the training part.
        model = AdviceClassifier().fit([texts[i] for i in train], y[train])
        # Predict the unseen test part (probability ≥ 0.5 means advice).
        preds[test] = (model.predict_proba([texts[i] for i in test]) >= 0.5).astype(np.int64)
    # Scores over all out-of-fold predictions.
    return metrics(y, preds)


# Train once per process.
@lru_cache
# The shared trained classifier.
def get_classifier() -> AdviceClassifier:
    # Labelled data.
    texts, y = load_dataset()
    # Train on all of it.
    return AdviceClassifier().fit(texts, y)
