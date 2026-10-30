"""Groq and Gemini through LangChain chat models.

LangChain is used here, and only here, for what it does well: one chat interface over
several vendors, and fallback from one vendor to another when a call fails (free-tier rate
limits are the usual cause). Agents still see the small `LLMProvider` protocol, so the
graph, the verifier and the tests do not depend on LangChain.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from aicfo.config import Settings
from aicfo.llm import LLMError, LLMProvider, OpenAICompatibleLLM

# The two hosted providers, in default order (Groq first: faster, more generous free tier).
VENDORS = ("groq", "gemini")


# Chat replies are a string, or (Gemini) a list of parts; keep only the text.
def _text(content: str | list[Any]) -> str:
    """Chat content is a string, or (Gemini) a list of parts; keep only the text parts."""
    # Plain string: nothing to do.
    if isinstance(content, str):
        # Use it as is.
        return content
    # Take the text of each part.
    parts = [p if isinstance(p, str) else p.get("text", "") for p in content]
    # Join the text parts; thinking/tool parts are dropped.
    return "".join(p for p in parts if isinstance(p, str))


# Adapts a LangChain chat model to our small LLMProvider interface (system + user → text).
class LangChainLLM:
    # Keep the model and a label.
    def __init__(self, model: Runnable[Any, Any], name: str) -> None:
        # A LangChain chat model, possibly with fallbacks attached.
        self._model = model
        # Label such as "groq:openai/gpt-oss-120b→gemini:…"; stored with each review run.
        self.name = name

    # Send a system and a user message; return the reply text.
    def complete(self, system: str, user: str) -> str:
        # Vendor SDKs raise many different error types.
        try:
            # One chat call (LangChain retries and falls back inside).
            msg = self._model.invoke([SystemMessage(system), HumanMessage(user)])
        # Any failure becomes one LLMError that the agents already handle.
        except Exception as exc:  # each vendor SDK raises its own error types
            # Callers fall back to firm policy or extractive answers.
            raise LLMError(f"LLM call failed: {type(exc).__name__}") from exc
        # The reply as clean text.
        return _text(msg.content).strip()


# Which vendors have an API key.
def configured_vendors(settings: Settings) -> list[str]:
    # The key for each vendor (None when unset).
    keys = {"groq": settings.groq_api_key, "gemini": settings.gemini_api_key}
    # Vendors with a key, in default order.
    return [v for v in VENDORS if keys[v] is not None]


# Create the LangChain chat model for a vendor.
def chat_model(vendor: str, settings: Settings) -> BaseChatModel:
    # Groq (OpenAI gpt-oss on Groq's fast hardware).
    if vendor == "groq":
        # Imported only when needed.
        from langchain_groq import ChatGroq

        # configured_vendors guarantees the key exists.
        assert settings.groq_api_key is not None
        # temperature 0 for repeatable answers; timeout and retries come from settings.
        return ChatGroq(
            model_name=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=0,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )
    # Google Gemini Flash.
    if vendor == "gemini":
        # Imported only when needed.
        from langchain_google_genai import ChatGoogleGenerativeAI

        # Key exists.
        assert settings.gemini_api_key is not None
        # No temperature: Gemini 3.6 models deprecate sampling parameters.
        # Gemini 3.x models reject sampling settings, so no temperature here.
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            timeout=settings.llm_timeout,
            max_retries=settings.llm_max_retries,
        )
    # Only groq and gemini are supported.
    raise ValueError(f"unknown vendor {vendor!r}")


# A readable name: "vendor:model".
def _label(vendor: str, settings: Settings) -> str:
    # Vendor and its configured model.
    return f"{vendor}:{settings.groq_model if vendor == 'groq' else settings.gemini_model}"


# One vendor, no fallback (the benchmark uses this to compare vendors fairly).
def single(vendor: str, settings: Settings) -> LangChainLLM:
    """One vendor, no fallback (used by the benchmark to compare vendors fairly)."""
    # Wrap it.
    return LangChainLLM(chat_model(vendor, settings), _label(vendor, settings))


# A chain of vendors: if the first fails, the same prompt goes to the next.
def with_fallbacks(order: Sequence[str], settings: Settings) -> LangChainLLM:
    # First vendor and the backups.
    primary, *rest = (chat_model(v, settings) for v in order)
    # LangChain's with_fallbacks tries the backups in order when the primary raises.
    model: Runnable[Any, Any] = primary.with_fallbacks(rest) if rest else primary
    # Wrap it with a label showing the order.
    return LangChainLLM(model, "→".join(_label(v, settings) for v in order))


# The provider the agents and RAG use, or None for the deterministic fallbacks.
def build_llm(settings: Settings) -> LLMProvider | None:
    """The provider the agents and RAG use, or None for the deterministic fallbacks."""
    # AICFO_LLM_PROVIDER: auto, groq, gemini, openai or none.
    choice = settings.llm_provider
    # Deliberately no model (CI, offline).
    if choice == "none":
        # Agents use firm policy; RAG uses extractive answers.
        return None
    # A self-hosted OpenAI-compatible server (e.g. Ollama)…
    if choice == "openai" or (
        choice == "auto" and settings.llm_base_url and not configured_vendors(settings)
    ):
        # …needs its address.
        if not settings.llm_base_url:
            # Fail loudly on a half-finished setup.
            raise ValueError("AICFO_LLM_PROVIDER=openai needs AICFO_LLM_BASE_URL")
        # Optional bearer key for that server.
        key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        # Use it.
        return OpenAICompatibleLLM(
            settings.llm_base_url, settings.llm_model, key, settings.llm_timeout
        )
    # Vendors that have keys.
    available = configured_vendors(settings)
    # Auto: use whatever keys exist.
    if choice == "auto":
        # No keys at all…
        if not available:
            # …so run without a model.
            return None
        # Groq first, Gemini as backup.
        order = available
    # A specific vendor was requested.
    else:
        # Requested a vendor without a key.
        if choice not in available:
            # Say which key is missing.
            raise ValueError(f"AICFO_LLM_PROVIDER={choice} but no API key is set for it")
        # Requested vendor first, the other as backup.
        order = [choice, *(v for v in available if v != choice)]
    # Fallback switched off.
    if not settings.llm_fallback:
        # Use only the first vendor.
        order = order[:1]
    # Build the chain.
    return with_fallbacks(order, settings)
