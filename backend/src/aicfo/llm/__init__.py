"""LLM providers. Only this package talks to model APIs (plan §3.2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import httpx


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


class LLMError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    """Any `/chat/completions` endpoint: Ollama (`http://localhost:11434/v1`), Groq, vLLM."""

    def __init__(
        self, base_url: str, model: str, api_key: str | None = None, timeout: float = 60.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = f"openai-compatible:{model}"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._timeout = timeout

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            r = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers,
                timeout=self._timeout,
            )
            r.raise_for_status()
            return str(r.json()["choices"][0]["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"LLM call failed: {type(exc).__name__}") from exc


class FakeLLM:
    """Deterministic stand-in for tests: returns a fixed reply or one built from the prompt."""

    def __init__(self, reply: str | Callable[[str, str], str]) -> None:
        self.name = "fake"
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._reply(system, user) if callable(self._reply) else self._reply
