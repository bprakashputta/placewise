"""Settings, loaded from environment variables and the .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

# Default models per provider: "fast" for extraction/scoring, "smart" for the agent and answers.
DEFAULT_MODELS = {
    "anthropic": {"fast": "claude-haiku-5-5", "smart": "claude-sonnet-5-5"},
    "openai": {"fast": "gpt-5-mini", "smart": "gpt-5"},
}

# USD per 1M tokens (input, output). These are placeholders: check them against the
# provider's pricing page before quoting any cost numbers. Tokens are always logged,
# so costs can be recomputed later.
PRICES_PER_MTOK = {
    "claude-haiku-5-5": (1.00, 5.00),
    "claude-sonnet-5-5": (3.00, 15.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_provider: str | None = None
    model_fast: str | None = None
    model_smart: str | None = None

    database_url: str = "postgresql://localhost:5432/aec_copilot"

    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384

    # Guardrails
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2          # retries on invalid JSON or transient errors
    match_concurrency: int = 4        # parallel LLM scoring calls
    agent_max_steps: int = 8
    agent_max_tokens_total: int = 60_000

    @property
    def provider(self) -> str:
        if self.llm_provider:
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        raise RuntimeError("No LLM key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")

    def model(self, tier: str) -> str:
        override = self.model_fast if tier == "fast" else self.model_smart
        return override or DEFAULT_MODELS[self.provider][tier]


@lru_cache
def get_settings() -> Settings:
    return Settings()
