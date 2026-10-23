"""FastAPI entry point.

Route layout (security boundary):
- `/api/*`  public app routes. The web container proxies ONLY this prefix to the browser.
- `/livez`  container liveness, internal only, used by the Docker healthcheck.
- `/docs`, `/openapi.json` and `/dev/*` exist only when APP_ENV=dev, and are never proxied.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Response
from langsmith import traceable

from . import __version__
from .config import get_settings
from .db import close_pool, open_pool
from .health import check_db, check_langsmith


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()


settings = get_settings()
DEV = settings.app_env == "dev"

app = FastAPI(
    title="Placewise API",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if DEV else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DEV else None,
)

api = APIRouter(prefix="/api")


@app.get("/livez", include_in_schema=False)
async def livez() -> dict:
    """Is the process up? It deliberately checks nothing external, so an outage at
    LangSmith never marks the container unhealthy."""
    return {"ok": True}


@api.get("/health")
async def health(response: Response) -> dict:
    """Readiness: are the API's dependencies reachable? Returns 503 if any is down.
    Details (versions, project names) are shown only in dev."""
    try:
        langsmith = await check_langsmith()
    except asyncio.TimeoutError:
        langsmith = {"ok": False, "detail": "timed out"}
    checks = {"api": {"ok": True, "detail": f"v{__version__}"}, "db": await check_db(), "langsmith": langsmith}
    ok = all(c["ok"] for c in checks.values())
    response.status_code = 200 if ok else 503
    if not DEV:
        checks = {k: {"ok": v["ok"], "detail": "connected" if v["ok"] else "unavailable"} for k, v in checks.items()}
    return {"ok": ok, "checks": checks}


app.include_router(api)

if DEV:
    @traceable(name="placewise.trace_check", run_type="chain")
    def _trace_check() -> dict:
        return {"message": "Placewise tracing works"}

    @app.post("/dev/trace", include_in_schema=True)
    async def dev_trace() -> dict:
        """Dev only: send one small test trace to LangSmith."""
        return await asyncio.to_thread(_trace_check)
