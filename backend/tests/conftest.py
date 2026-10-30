"""Tests never call real LLM or broker APIs, even if a developer's .env has keys (CLAUDE.md).

Environment variables beat the .env file, so setting them here wins over anything in
backend/.env (API keys, the automation token that `make init-env` generates, webhook URLs).
A blank value counts as "not configured". The DB tests run on in-memory SQLite, or on
Postgres when AICFO_TEST_DATABASE_URL is set (CI's database job).
"""

import os

os.environ["AICFO_ENV"] = "test"  # relaxes the "secret required" rules used in staging/prod
os.environ["AICFO_LLM_PROVIDER"] = "none"  # never call Groq or Gemini from tests
os.environ["AICFO_DATABASE_URL"] = os.environ.get("AICFO_TEST_DATABASE_URL", "sqlite://")
os.environ["AICFO_LOCAL_KEKS"] = "k1:" + "A" * 43 + "="  # fixed test-only key-encryption key
os.environ["AICFO_DHAN_MODE"] = "sandbox"  # recorded responses only, never the real broker
# Blank these out so a developer's real values in backend/.env cannot change test behaviour.
for key in (
    "AICFO_AUTOMATION_TOKEN",
    "AICFO_JWT_SECRET",
    "AICFO_N8N_WEBHOOK_URL",
    "AICFO_N8N_WEBHOOK_SECRET",
    "AICFO_GROQ_API_KEY",
    "AICFO_GEMINI_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
):
    os.environ[key] = ""
