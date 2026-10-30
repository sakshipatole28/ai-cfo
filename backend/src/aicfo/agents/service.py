from __future__ import annotations

from functools import lru_cache

from aicfo.agents.copilot import Copilot
from aicfo.agents.review import ReviewPipeline
from aicfo.rag.service import get_rag


# Build the review pipeline once per process.
@lru_cache
# The shared LangGraph review pipeline.
def get_pipeline() -> ReviewPipeline:
    # The shared RAG service (retriever + LLM).
    rag = get_rag()
    # Agents use the same retriever and model as the rulebook.
    return ReviewPipeline(rag.retriever, rag.answerer.llm)


# Build the Copilot once per process.
@lru_cache
# The shared tool-using Copilot.
def get_copilot() -> Copilot:
    # The shared RAG service.
    rag = get_rag()
    # Copilot uses the answerer for rules and the same model.
    return Copilot(rag.answerer, rag.answerer.llm)
