"""FastAPI entry point."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from langsmith import traceable

from . import __version__
from .db import close_pool, open_pool
from .health import check_db, check_langsmith


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()


app = FastAPI(title="Placewise API", version=__version__, lifespan=lifespan)


@app.get("/health")
async def health(response: Response) -> dict:
    """Liveness and dependency status. Returns 503 if any dependency is down."""
    try:
        langsmith = await check_langsmith()
    except asyncio.TimeoutError:
        langsmith = {"ok": False, "detail": "timed out"}
    checks = {"api": {"ok": True, "detail": f"v{__version__}"}, "db": await check_db(), "langsmith": langsmith}
    ok = all(c["ok"] for c in checks.values())
    response.status_code = 200 if ok else 503
    return {"ok": ok, "checks": checks}


@traceable(name="placewise.trace_check", run_type="chain")
def _trace_check() -> dict:
    return {"message": "Placewise tracing works"}


@app.post("/health/trace")
async def health_trace() -> dict:
    """Send one small test trace to LangSmith, to confirm the project shows up there."""
    return await asyncio.to_thread(_trace_check)
