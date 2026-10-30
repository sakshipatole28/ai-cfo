"""Text utilities shared by indexing, retrieval and answer verification."""

from __future__ import annotations

import re

import snowballstemmer

# Very common words that carry no meaning for search (the, is, of…); they are ignored.
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

# A word token: letters, digits or ₹, optionally with a decimal part (so 1.25 stays one token).
_TOKEN = re.compile(r"[a-z0-9₹]+(?:\.[0-9]+)?")
# A sentence boundary: end punctuation followed by a capital letter, digit, ₹ or quote.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z₹0-9\"'(])")
# A number in text: optional ₹, digits with commas, optional decimals, optional %.
_NUMBER = re.compile(r"(?<![\w.])₹?\s?\d[\d,]*(?:\.\d+)?%?")


# English Snowball stemmer (Porter2).
_STEMMER = snowballstemmer.stemmer("english")


# Reduce a word to its root so "gains" matches "gain".
def _stem(token: str) -> str:
    """Snowball (Porter2) stemming so 'distribute'/'distribution' and 'gains'/'gain' match."""
    # Leave numbers alone.
    return token if any(ch.isdigit() for ch in token) else str(_STEMMER.stemWord(token))


# Redaction placeholders such as [REDACTED_PAN] carry no meaning for search.
_PLACEHOLDER = re.compile(r"\[redacted_[a-z]+\]")


# Break text into searchable terms: lower-case, stemmed, no stop words.
def tokenize(text: str) -> list[str]:
    """Lower-case word tokens, stemmed, without stop words or redaction placeholders."""
    # Lower-case and remove redaction placeholders.
    cleaned = _PLACEHOLDER.sub(" ", text.lower())
    # Tokens that are not stop words, each stemmed.
    return [_stem(t) for t in _TOKEN.findall(cleaned) if t not in STOPWORDS]


# Split a passage into sentences (used to quote the best ones).
def sentences(text: str) -> list[str]:
    # Trimmed, non-empty sentences.
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


# Every number in a text, normalised so "₹1,50,000" and "150000" compare equal.
def numbers(text: str) -> set[str]:
    """Normalised numeric facts in a text: '₹1.25' -> '1.25', '1,50,000' -> '150000', '20%' -> '20'."""
    # Normalised numbers seen.
    found: set[str] = set()
    # Each number-like string.
    for raw in _NUMBER.findall(text):
        # Strip ₹, commas and % signs.
        value = raw.replace("₹", "").replace(",", "").replace("%", "").strip()
        # Ignore empty strings.
        if value:
            # Drop trailing zeros after a decimal point (1.50 → 1.5).
            found.add(value.rstrip("0").rstrip(".") if "." in value else value)
    # The set of numbers.
    return found


# Models write citation markers in different bracket styles: gpt-oss uses 【1】, some use ［1］.
_CITE_VARIANTS = re.compile(r"[【［〔]\s*(\d+)\s*[】］〕]")


def normalise_citations(text: str) -> str:
    """Rewrite 【1】 / ［1］ / 〔1〕 as [1], the form the verifier checks. Changes nothing else."""
    return _CITE_VARIANTS.sub(r"[\1]", text)
