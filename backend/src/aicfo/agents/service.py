from __future__ import annotations

from functools import lru_cache

from aicfo.agents.copilot import Copilot
from aicfo.agents.review import ReviewPipeline
from aicfo.rag.service import get_rag


@lru_cache
def get_pipeline() -> ReviewPipeline:
    rag = get_rag()
    return ReviewPipeline(rag.retriever, rag.answerer.llm)


@lru_cache
def get_copilot() -> Copilot:
    rag = get_rag()
    return Copilot(rag.answerer, rag.answerer.llm)
