"""Text utilities shared by indexing, retrieval and answer verification."""

from __future__ import annotations

import re

import snowballstemmer

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "me",
        "must",
        "my",
        "of",
        "on",
        "or",
        "our",
        "shall",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "per",
        "also",
        "any",
        "each",
        "such",
    ]
)

_TOKEN = re.compile(r"[a-z0-9₹]+(?:\.[0-9]+)?")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z₹0-9\"'(])")
_NUMBER = re.compile(r"(?<![\w.])₹?\s?\d[\d,]*(?:\.\d+)?%?")


_STEMMER = snowballstemmer.stemmer("english")


def _stem(token: str) -> str:
    """Snowball (Porter2) stemming so 'distribute'/'distribution' and 'gains'/'gain' match."""
    return token if any(ch.isdigit() for ch in token) else str(_STEMMER.stemWord(token))


_PLACEHOLDER = re.compile(r"\[redacted_[a-z]+\]")


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens, stemmed, without stop words or redaction placeholders."""
    cleaned = _PLACEHOLDER.sub(" ", text.lower())
    return [_stem(t) for t in _TOKEN.findall(cleaned) if t not in STOPWORDS]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def numbers(text: str) -> set[str]:
    """Normalised numeric facts in a text: '₹1.25' -> '1.25', '1,50,000' -> '150000', '20%' -> '20'."""
    found: set[str] = set()
    for raw in _NUMBER.findall(text):
        value = raw.replace("₹", "").replace(",", "").replace("%", "").strip()
        if value:
            found.add(value.rstrip("0").rstrip(".") if "." in value else value)
    return found
