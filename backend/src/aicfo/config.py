from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AICFO_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://aicfo:aicfo@localhost:5432/aicfo"
    # "id1:<base64-32-bytes>,id2:<...>". Dev/test only; prod uses OpenBao Transit.
    local_keks: SecretStr | None = None
    active_kek_id: str = "k1"

    # RAG
    kb_dir: Path = REPO_ROOT / "data" / "kb"
    rag_embedder: Literal["hashing", "fastembed"] = "hashing"
    # Any OpenAI-compatible endpoint, e.g. Ollama at http://localhost:11434/v1. Unset = extractive answers.
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str = "llama3.1:8b"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Live broker connection. "sandbox" runs the full flow against recorded responses.
    dhan_mode: Literal["off", "sandbox", "live"] = "sandbox"
    dhan_app_id: str | None = None
    dhan_app_secret: SecretStr | None = None
    dhan_client_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
