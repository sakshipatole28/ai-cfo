from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from aicfo.config import Settings, get_settings
from aicfo.llm import LLMProvider, OpenAICompatibleLLM
from aicfo.rag.answer import Answerer
from aicfo.rag.corpus import Chunk, Document, load_corpus
from aicfo.rag.embeddings import Embedder, FastEmbedEmbedder, HashingEmbedder
from aicfo.rag.retriever import HybridRetriever


@dataclass
class RagService:
    documents: list[Document]
    chunks: list[Chunk]
    retriever: HybridRetriever
    answerer: Answerer


def build(settings: Settings) -> RagService:
    docs, chunks = load_corpus(settings.kb_dir)
    embedder: Embedder = (
        FastEmbedEmbedder() if settings.rag_embedder == "fastembed" else HashingEmbedder()
    )
    retriever = HybridRetriever(chunks, embedder)
    llm: LLMProvider | None = None
    if settings.llm_base_url:
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        llm = OpenAICompatibleLLM(settings.llm_base_url, settings.llm_model, key)
    return RagService(docs, chunks, retriever, Answerer(retriever, llm))


@lru_cache
def get_rag() -> RagService:
    return build(get_settings())
