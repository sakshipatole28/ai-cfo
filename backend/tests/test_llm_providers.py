from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import BaseMessage

from aicfo.config import Settings
from aicfo.llm import FakeLLM, LLMError, OpenAICompatibleLLM
from aicfo.llm.bench import run, table
from aicfo.llm.providers import LangChainLLM, _text, build_llm, configured_vendors
from aicfo.rag.service import get_rag


class Failing(FakeListChatModel):
    """A chat model that always fails, like a rate-limited free tier."""

    def _call(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> str:
        raise RuntimeError("429 rate limited")


def settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {"llm_provider": "auto", "groq_api_key": None, "gemini_api_key": None}
    return Settings(_env_file=None, **{**base, **kw})  # type: ignore[call-arg]


def test_no_keys_means_deterministic_mode() -> None:
    assert build_llm(settings()) is None
    assert build_llm(settings(llm_provider="none", groq_api_key="gsk_test")) is None
    assert build_llm(settings(groq_api_key="", gemini_api_key="  ")) is None  # blank .env lines


def test_auto_prefers_groq_and_falls_back_to_gemini() -> None:
    s = settings(groq_api_key="gsk_test", gemini_api_key="gem_test")
    assert configured_vendors(s) == ["groq", "gemini"]
    llm = build_llm(s)
    assert llm is not None and llm.name == f"groq:{s.groq_model}→gemini:{s.gemini_model}"


def test_explicit_provider_goes_first_and_fallback_can_be_disabled() -> None:
    s = settings(llm_provider="gemini", groq_api_key="g", gemini_api_key="m")
    assert build_llm(s).name.startswith("gemini:")  # type: ignore[union-attr]
    s = settings(llm_provider="gemini", groq_api_key="g", gemini_api_key="m", llm_fallback=False)
    assert "→" not in build_llm(s).name  # type: ignore[union-attr]


def test_missing_key_for_chosen_provider_is_an_error() -> None:
    with pytest.raises(ValueError, match="no API key"):
        build_llm(settings(llm_provider="groq"))


def test_openai_compatible_endpoint_still_supported() -> None:
    llm = build_llm(settings(llm_base_url="http://localhost:11434/v1"))
    assert isinstance(llm, OpenAICompatibleLLM)


def test_fallback_runs_when_primary_fails() -> None:
    primary = Failing(responses=["unused"])
    backup = FakeListChatModel(responses=["from backup"])
    llm = LangChainLLM(primary.with_fallbacks([backup]), "test")
    assert llm.complete("system", "user") == "from backup"


def test_vendor_errors_become_llm_error() -> None:
    with pytest.raises(LLMError):
        LangChainLLM(Failing(responses=["x"]), "test").complete("s", "u")


def test_gemini_content_parts_are_joined() -> None:
    assert _text([{"type": "text", "text": "a"}, "b", {"type": "thought"}]) == "ab"


def test_benchmark_scores_guard_survival_without_network() -> None:
    good = FakeLLM('{"selected": []}')
    bad = FakeLLM("not json and 42 unsupported numbers")
    retriever = get_rag().retriever
    a = run(good, retriever, clients=1, questions=3)
    b = run(bad, retriever, clients=1, questions=3)
    assert a.analyst_json_ok == 1.0 and b.analyst_json_ok == 0.0
    assert a.errors == 0 and a.calls > 0
    assert table([a, b]).count("\n") == 3
