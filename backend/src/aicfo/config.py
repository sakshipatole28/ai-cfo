from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AICFO_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://aicfo:aicfo@localhost:5432/aicfo"
    # "id1:<base64-32-bytes>,id2:<...>". Dev/test only; prod uses OpenBao Transit.
    local_keks: SecretStr | None = None
    active_kek_id: str = "k1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
