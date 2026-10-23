"""App settings, read from environment variables.

Docker Compose maps the owner's .env names (PLACEWISE_*) to the standard names below,
so the code and third-party SDKs (Anthropic, Voyage, LangSmith) all read the same variables.
"""
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: Literal["dev", "prod"] = "prod"  # safe default: dev-only routes stay off unless asked
    database_url: str
    app_secret_key: SecretStr

    langsmith_api_key: SecretStr | None = None
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = "placewise"
    langsmith_tracing: bool = True

    anthropic_api_key: SecretStr | None = None
    voyage_api_key: SecretStr | None = None

    daily_llm_spend_cap_usd: float = 10.0
    cookie_secure: bool = False   # True when served over HTTPS (the public tunnel link)
    trust_cloudflare_ip: bool = False   # True only when traffic arrives through the Cloudflare tunnel

    db_pool_min: int = 1
    db_pool_max: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
