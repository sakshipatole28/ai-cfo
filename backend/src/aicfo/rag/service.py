from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from aicfo.config import Settings, get_settings
from aicfo.llm.providers import build_llm
from aicfo.rag.answer import Answerer
from aicfo.rag.corpus import Chunk, Document, load_corpus
from aicfo.rag.embeddings import Embedder, FastEmbedEmbedder, HashingEmbedder
from aicfo.rag.retriever import HybridRetriever


# Everything the RAG feature needs, built once.
@dataclass
class RagService:
    # Source documents.
    documents: list[Document]
    # All passages.
    chunks: list[Chunk]
    # Hybrid search.
    retriever: HybridRetriever
    # Guarded, cited answers.
    answerer: Answerer


# Create the RAG service from settings.
def build(settings: Settings) -> RagService:
    # Load and chunk the knowledge base.
    docs, chunks = load_corpus(settings.kb_dir)
    # Real bge-small embeddings if configured, else the offline hashing fallback.
    embedder: Embedder = (
        FastEmbedEmbedder() if settings.rag_embedder == "fastembed" else HashingEmbedder()
    )
    # Index the passages for keyword and meaning search.
    retriever = HybridRetriever(chunks, embedder)
    # The answerer uses Groq/Gemini when keys exist, else extractive answers.
    return RagService(docs, chunks, retriever, Answerer(retriever, build_llm(settings)))


# Build once per process and reuse (indexing is the slow part).
@lru_cache
# Shared RAG service.
def get_rag() -> RagService:
    # Build from the current settings.
    return build(get_settings())
