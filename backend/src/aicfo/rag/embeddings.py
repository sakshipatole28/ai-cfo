"""Dense embedders behind one interface.

* `FastEmbedEmbedder`: BAAI/bge-small-en-v1.5 (384-dim, ONNX on CPU). Install with
  `uv sync --extra models`. Runs locally, so no text leaves the server.
* `HashingEmbedder`: deterministic feature hashing of words and word pairs. No
  model download, used in CI and as an offline fallback.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Sequence
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from aicfo.rag.text import tokenize

# A 2-D array of float32: one row per text.
Matrix = NDArray[np.float32]


# What every embedder must offer: embed passages and embed a query.
class Embedder(Protocol):
    # Shown in the console.
    name: str

    # Vectors for many passages.
    def embed_documents(self, texts: Sequence[str]) -> Matrix: ...

    # Vector for one query.
    def embed_query(self, text: str) -> Matrix: ...


# Scale each vector to length 1, so a dot product equals cosine similarity.
def _normalise(m: Matrix) -> Matrix:
    # Length of each row.
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    # Avoid dividing by zero for empty text.
    norms[norms == 0] = 1.0
    # Unit vectors.
    return (m / norms).astype(np.float32)


# Offline fallback: hashes words and word pairs into a fixed-size vector. No model download.
class HashingEmbedder:
    # dim = vector size.
    def __init__(self, dim: int = 1024) -> None:
        # Number of dimensions.
        self.dim = dim
        # Label.
        self.name = f"hashing-{dim}"

    # Vector for one text.
    def _vector(self, text: str) -> NDArray[np.float32]:
        # Start empty.
        v = np.zeros(self.dim, dtype=np.float32)
        # Stemmed words without stop words.
        tokens = tokenize(text)
        # Single words plus neighbouring pairs (captures a little word order).
        features = tokens + [f"{a} {b}" for a, b in itertools.pairwise(tokens)]
        # Each feature.
        for feat in features:
            # A stable 64-bit hash of the feature.
            h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "little")
            # Add ±1 at the hashed position (the sign comes from another bit, so collisions tend to cancel).
            v[h % self.dim] += 1.0 if (h >> 63) == 0 else -1.0
        # Dampen large counts with a log.
        return np.sign(v) * np.log1p(np.abs(v))

    # Vectors for many texts, normalised.
    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        # Stack and normalise.
        return _normalise(np.stack([self._vector(t) for t in texts]))

    # A query is embedded like a one-text document.
    def embed_query(self, text: str) -> Matrix:
        # One row.
        return self.embed_documents([text])


# Real semantic embeddings: BAAI/bge-small-en-v1.5 via ONNX on CPU, running locally.
class FastEmbedEmbedder:
    # Load the model (downloaded on first use).
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5") -> None:
        # fastembed is an optional dependency.
        try:
            # Import only when asked for.
            from fastembed import TextEmbedding
        # Explain how to install it.
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("fastembed is not installed; run `uv sync --extra models`") from exc
        # The loaded model.
        self._model: Any = TextEmbedding(model_name=model)
        # Label.
        self.name = model

    # Vectors for passages, using the model's passage mode.
    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        # Normalised vectors.
        return _normalise(np.array(list(self._model.passage_embed(list(texts))), dtype=np.float32))

    # Vector for a query, using the model's query mode.
    def embed_query(self, text: str) -> Matrix:
        # Normalised vector.
        return _normalise(np.array(list(self._model.query_embed([text])), dtype=np.float32))
