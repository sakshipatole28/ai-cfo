from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository root (three folders above this file).
REPO_ROOT = Path(__file__).resolve().parents[3]

# Allowed values of AICFO_LLM_PROVIDER.
LLMProviderName = Literal["auto", "none", "openai", "groq", "gemini"]


# Every setting, read from environment variables (prefix AICFO_) or backend/.env.
class Settings(BaseSettings):
    # Read AICFO_* variables and the .env file; ignore unknown ones.
    model_config = SettingsConfigDict(
        env_prefix="AICFO_", env_file=".env", extra="ignore", populate_by_name=True
    )

    # dev, test, staging or prod; stricter rules apply outside dev/test.
    env: Literal["dev", "test", "staging", "prod"] = "dev"
    # Postgres (Docker Compose, Supabase or Neon). `postgres://` URLs are normalised to psycopg.
    # Postgres (or SQLite for tests).
    database_url: str = "postgresql+psycopg://aicfo:aicfo@localhost:5432/aicfo"
    # "id1:<base64-32-bytes>,id2:<...>". Dev/test only; prod uses OpenBao Transit.
    # Key-encryption keys for firm data keys.
    local_keks: SecretStr | None = None
    # Which key is used for new wraps.
    active_kek_id: str = "k1"

    # RAG
    # Folder of rulebook documents.
    kb_dir: Path = REPO_ROOT / "data" / "kb"
    # hashing (offline) or fastembed (real semantic model).
    rag_embedder: Literal["hashing", "fastembed"] = "hashing"

    # LLM. "auto" picks Groq, then Gemini, then `llm_base_url`, from whichever is configured;
    # "none" keeps the deterministic firm policy and extractive answers (CI, offline demos).
    # auto, groq, gemini, openai or none.
    llm_provider: LLMProviderName = "auto"
    # When the primary provider fails (rate limit, outage), retry the call on the other one.
    # Retry on the other provider if the first fails.
    llm_fallback: bool = True
    # Seconds before a model call gives up.
    llm_timeout: float = 60.0
    # Automatic retries per call.
    llm_max_retries: int = 2
    # Groq key (AICFO_GROQ_API_KEY or GROQ_API_KEY).
    groq_api_key: SecretStr | None = Field(
        None, validation_alias=AliasChoices("AICFO_GROQ_API_KEY", "GROQ_API_KEY")
    )
    # Groq model.
    groq_model: str = "openai/gpt-oss-120b"
    # Gemini key (AICFO_GEMINI_API_KEY, GEMINI_API_KEY or GOOGLE_API_KEY).
    gemini_api_key: SecretStr | None = Field(
        None,
        validation_alias=AliasChoices("AICFO_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )
    # Gemini model.
    gemini_model: str = "gemini-3-flash-preview"
    # Any OpenAI-compatible endpoint, e.g. Ollama at http://localhost:11434/v1.
    # Address of a self-hosted OpenAI-compatible server.
    llm_base_url: str | None = None
    # Its key, if any.
    llm_api_key: SecretStr | None = None
    # Its model name.
    llm_model: str = "llama3.1:8b"
    # Browser origins allowed to call the API.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Sign-in. HS256 key for session tokens; required outside dev/test.
    # Signs session tokens.
    jwt_secret: SecretStr | None = None
    # How long a sign-in lasts.
    session_hours: int = 12
    # New firms get a copy of the synthetic demo book so the console has clients to review.
    # Give new firms the synthetic book.
    seed_new_firms: bool = True

    # Automation (n8n). Bearer token n8n sends to /v1/pipeline/* and review runs; the
    # webhook receives review events (IDs and counts only, never names or amounts).
    # Bearer token n8n uses.
    automation_token: SecretStr | None = None
    # Where review events are sent.
    n8n_webhook_url: str | None = None
    # Signs those events.
    n8n_webhook_secret: SecretStr | None = None

    # Live broker connection. "sandbox" runs the full flow against recorded responses.
    # off, sandbox or live broker connection.
    dhan_mode: Literal["off", "sandbox", "live"] = "sandbox"
    # Dhan app id.
    dhan_app_id: str | None = None
    # Dhan app secret.
    dhan_app_secret: SecretStr | None = None
    # Dhan client id.
    dhan_client_id: str | None = None

    @field_validator(
        "groq_api_key",
        "gemini_api_key",
        "llm_api_key",
        "llm_base_url",
        "automation_token",
        "n8n_webhook_url",
        "n8n_webhook_secret",
        "jwt_secret",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, v: object) -> object:
        """`AICFO_GROQ_API_KEY=` (as in .env.example) means "not configured", not an empty key."""
        return None if isinstance(v, str) and not v.strip() else v


# Read settings once.
@lru_cache
# The shared settings object.
def get_settings() -> Settings:
    # Read the environment.
    return Settings()
