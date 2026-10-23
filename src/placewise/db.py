"""Database connection pool (async, shared by every request)."""
from psycopg_pool import AsyncConnectionPool

from .config import get_settings

_pool: AsyncConnectionPool | None = None


async def open_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = AsyncConnectionPool(
            s.database_url,
            min_size=s.db_pool_min,
            max_size=s.db_pool_max,
            open=False,
            kwargs={"connect_timeout": 5},
        )
        # wait=False: the API starts even if the database is still booting.
        # /health reports the database as down until it can connect.
        await _pool.open(wait=False)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not open")
    return _pool
