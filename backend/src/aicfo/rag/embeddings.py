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

Matrix = NDArray[np.float32]


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: Sequence[str]) -> Matrix: ...

    def embed_query(self, text: str) -> Matrix: ...


def _normalise(m: Matrix) -> Matrix:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


class HashingEmbedder:
    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim
        self.name = f"hashing-{dim}"

    def _vector(self, text: str) -> NDArray[np.float32]:
        v = np.zeros(self.dim, dtype=np.float32)
        tokens = tokenize(text)
        features = tokens + [f"{a} {b}" for a, b in itertools.pairwise(tokens)]
        for feat in features:
            h = int.from_bytes(hashlib.blake2b(feat.encode(), digest_size=8).digest(), "little")
            v[h % self.dim] += 1.0 if (h >> 63) == 0 else -1.0
        return np.sign(v) * np.log1p(np.abs(v))

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        return _normalise(np.stack([self._vector(t) for t in texts]))

    def embed_query(self, text: str) -> Matrix:
        return self.embed_documents([text])


class FastEmbedEmbedder:
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5") -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("fastembed is not installed; run `uv sync --extra models`") from exc
        self._model: Any = TextEmbedding(model_name=model)
        self.name = model

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        return _normalise(np.array(list(self._model.passage_embed(list(texts))), dtype=np.float32))

    def embed_query(self, text: str) -> Matrix:
        return _normalise(np.array(list(self._model.query_embed([text])), dtype=np.float32))
