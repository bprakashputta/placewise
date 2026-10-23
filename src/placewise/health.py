"""Health checks for the API, the database (with pgvector) and LangSmith.

The LangSmith check is a network call, so its result is cached for a short time.
That keeps /health fast and avoids hammering LangSmith when something polls it.
"""
import asyncio
import time

from langsmith import Client

from .config import get_settings
from .db import pool

_LANGSMITH_TTL_S = 60
_langsmith_cache: tuple[float, dict] | None = None


async def check_db() -> dict:
    try:
        async with pool().connection(timeout=3) as conn:
            cur = await conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            row = await cur.fetchone()
        if row is None:
            return {"ok": False, "detail": "connected, but the pgvector extension is not installed"}
        return {"ok": True, "detail": f"connected, pgvector {row[0]}"}
    except Exception as e:  # report the reason without exposing connection strings
        return {"ok": False, "detail": f"cannot connect ({type(e).__name__})"}


def _check_langsmith_sync() -> dict:
    s = get_settings()
    if s.langsmith_api_key is None:
        return {"ok": False, "detail": "LANGSMITH_API_KEY not set"}
    try:
        client = Client(api_url=s.langsmith_endpoint, api_key=s.langsmith_api_key.get_secret_value())
        next(iter(client.list_projects(limit=1)), None)  # cheap authenticated call
        tracing = "on" if s.langsmith_tracing else "off"
        return {"ok": True, "detail": f"authenticated, tracing {tracing}, project '{s.langsmith_project}'"}
    except Exception as e:
        return {"ok": False, "detail": f"cannot reach LangSmith ({type(e).__name__})"}


async def check_langsmith() -> dict:
    global _langsmith_cache
    now = time.monotonic()
    if _langsmith_cache and now - _langsmith_cache[0] < _LANGSMITH_TTL_S:
        return _langsmith_cache[1]
    result = await asyncio.wait_for(asyncio.to_thread(_check_langsmith_sync), timeout=10)
    _langsmith_cache = (now, result)
    return result
