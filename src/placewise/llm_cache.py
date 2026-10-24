"""LangChain response cache in Postgres: an identical Claude request is answered from the database for $0.

LangChain's `BaseCache` interface (the same one `set_llm_cache` and `ChatAnthropic(cache=...)` use), stored
in our Postgres so it survives deploys and is shared by the api and workers. The key covers everything
that affects the answer: model and settings, the tool schema (structured output) and every message, so a
new prompt version, a different job order or a changed resume never hits an old entry.

Used for match scoring, the job order builder, Ask answers, question understanding and chat routing.
Re-running a match on the same job order, or asking the same question about the same results, then costs
nothing and returns the same verdicts. Resume extraction has its own content-hash cache (extraction_cache).

Only complete answers that pass the expected Pydantic schema are stored (right tool, valid arguments,
not cut off at max_tokens), so a failed or malformed answer is never replayed.

What it holds: derived resume text (the anonymized profile and job order in the keys' source, the model's
quotes and summaries in the values; Ask answers also include candidate names). Never contact details,
which are kept out of blind text and the searchable sections. Rows expire after LLM_RESPONSE_CACHE_DAYS
(default 7) and are deleted by purge_expired() at api startup and hourly in the worker.
Cache errors are logged and ignored: the call simply goes to the API.
A hit is visible in usage_metadata as total_cost == 0 (set by LangChain), and logged as status 'cache_hit'.
"""
import hashlib
import logging
import warnings
from typing import Any, Sequence

from pydantic import BaseModel, ValidationError

from langchain_core.caches import BaseCache
from langchain_core.load import dumps, loads
from langchain_core.outputs import ChatGeneration, Generation

from .config import get_settings
from .db import pool

log = logging.getLogger(__name__)


def _key(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def cacheable(gens: Sequence[Generation], schema: type[BaseModel] | None = None) -> bool:
    """Store only complete structured answers: a tool call, not cut off, and (given the schema) arguments
    that validate, so a malformed answer can't be replayed for days."""
    if not gens:
        return False
    for g in gens:
        if not isinstance(g, ChatGeneration):
            return False
        msg = g.message
        calls = getattr(msg, "tool_calls", None)
        if not calls:
            return False
        if (msg.response_metadata or {}).get("stop_reason") == "max_tokens":
            return False
        if schema is not None:
            if calls[0].get("name") != schema.__name__:
                return False
            try:
                schema.model_validate(calls[0].get("args") or {})
            except ValidationError:
                return False
    return True


class PostgresLLMCache(BaseCache):
    def __init__(self, ttl_days: int, schema: type[BaseModel] | None = None):
        self.ttl_days = ttl_days
        self.schema = schema   # the structured-output model; answers must validate to be stored

    # The app only uses async calls (ainvoke); the sync interface is a no-op, i.e. always a miss.
    def lookup(self, prompt: str, llm_string: str) -> Any:
        return None

    def update(self, prompt: str, llm_string: str, return_val: Any) -> None:
        return None

    def clear(self, **kwargs: Any) -> None:
        return None

    async def alookup(self, prompt: str, llm_string: str) -> Any:
        try:
            async with pool().connection() as conn:
                cur = await conn.execute(
                    """UPDATE llm_response_cache SET hits = hits + 1, last_hit_at = now()
                       WHERE prompt_key = %s AND llm_key = %s AND created_at > now() - make_interval(days => %s)
                       RETURNING value""", (_key(prompt), _key(llm_string), self.ttl_days))
                row = await cur.fetchone()
            if not row:
                return None
            with warnings.catch_warnings():   # langchain_core.load prints a beta notice on every call
                warnings.simplefilter("ignore")
                return loads(row[0])
        except Exception as e:   # never let the cache break a call
            log.warning("llm cache lookup failed: %s", e)
            return None

    async def aupdate(self, prompt: str, llm_string: str, return_val: Any) -> None:
        if not cacheable(return_val, self.schema):
            return
        try:
            async with pool().connection() as conn:
                await conn.execute(
                    """INSERT INTO llm_response_cache (prompt_key, llm_key, value) VALUES (%s, %s, %s)
                       ON CONFLICT (prompt_key, llm_key) DO UPDATE SET value = EXCLUDED.value, created_at = now(),
                       hits = 0, last_hit_at = NULL""",
                    (_key(prompt), _key(llm_string), dumps(list(return_val))))
        except Exception as e:
            log.warning("llm cache update failed: %s", e)

    async def aclear(self, **kwargs: Any) -> None:
        async with pool().connection() as conn:
            await conn.execute("DELETE FROM llm_response_cache")


def response_cache(schema: type[BaseModel] | None = None) -> PostgresLLMCache | bool:
    """The cache to pass as ChatAnthropic(cache=...); False disables it (LLM_RESPONSE_CACHE_DAYS=0)."""
    days = get_settings().llm_response_cache_days
    return PostgresLLMCache(days, schema) if days > 0 else False


async def purge_expired() -> int:
    """Delete expired rows (lookups already ignore them; this keeps derived resume text from lingering)."""
    days = max(get_settings().llm_response_cache_days, 0)
    async with pool().connection() as conn:
        cur = await conn.execute("DELETE FROM llm_response_cache WHERE created_at < now() - make_interval(days => %s)",
                                 (days,))
        return cur.rowcount
