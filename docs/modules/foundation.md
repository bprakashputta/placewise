# Module: Foundation (Block 0)

## Purpose (plain words)
Block 0 has no recruiting features yet. It builds the base everything else runs on: three containers (database, API, web portal) that start with one command, talk to each other safely, and show a **System status** page that answers one question: *is every piece connected?*

For an admin (Admin → System status), this is the page that says "All systems operational", or tells you which piece is down. For the owner, it proves the full path browser → web → api → db (and LangSmith tracing) works before any AI logic is added on top.

## Services
| Service | Image / build | What it does | Host port |
|---|---|---|---|
| `db` | `pgvector/pgvector:0.8.1-pg17` | Postgres 17 with the `vector` extension. Data in the named volume `db_data`. `001-extensions.sql` runs `CREATE EXTENSION vector` once, when the volume is first created. | **None** (the host has its own Postgres on 5432; uncomment `127.0.0.1:5433` only to debug) |
| `api` | `docker/api.Dockerfile` (uv, Python 3.12) | FastAPI app (`placewise.main:app`). Runs as non-root user `app` (uid 1000). In dev, `uvicorn --reload` with `./src` mounted. Starts after `db` is healthy. | `127.0.0.1:8000` (local only) |
| `web` | `web/Dockerfile` (`node:22-alpine`) | Next.js 16.4.2 dev server. Serves the UI and proxies `/api/*` to the api. | `127.0.0.1:3000` (local only) |

Diagrams: [architecture](../diagrams/architecture.md) · [deployment](../diagrams/deployment.md) · [health-check sequence](../diagrams/sequence-health-check.md)

## Request flow
1. The browser loads the portal from the `web` container (`/` redirects to the dashboard or login; the status check lives at Admin → System status, `/admin/system`).
2. The `SystemStatusView` client component calls `fetch("/api/health")` on the **same origin** (no CORS, no API URL in the browser).
3. Next.js `rewrites()` forwards `/api/:path*` to `http://api:8000/api/:path*` over the internal Docker network.
4. The api runs the db and LangSmith checks and returns JSON (200 if all OK, 503 if anything is down).
5. The page shows each service as "Connected" or "Down" with a **Recheck** button.

## Routes
| Route | Exposed via web (:3000)? | When it exists | Purpose |
|---|---|---|---|
| `/api/health` | Yes | Always | Readiness: api + db (with pgvector) + LangSmith |
| `/livez` | No | Always | Liveness: process is up; checks nothing external |
| `/docs`, `/openapi.json` | No | `APP_ENV=dev` only | API docs at `localhost:8000/docs` |
| `/dev/trace` (POST) | No | `APP_ENV=dev` only | Sends one small test trace to LangSmith |
| `/redoc` | No | Never (disabled) | — |

## Health and liveness design
Two separate checks, because they answer different questions ([ADR 004](../decisions/004-liveness-vs-readiness.md)):

- **`/livez` (liveness):** returns `{"ok": true}` and touches nothing else. The api image's Docker `HEALTHCHECK` calls it every 10s. A LangSmith or db outage must never make Docker think the api process itself is broken.
- **`/api/health` (readiness):** returns `{"ok": bool, "checks": {"api", "db", "langsmith"}}`.
  - **db:** borrows a pool connection (3s wait, 5s connect timeout) and reads `extversion` of `vector` from `pg_extension`. Reports "connected, pgvector 0.8.1", "pgvector extension is not installed", or "cannot connect (<ExceptionType>)". The connection string is never included.
  - **LangSmith:** a cheap authenticated call (`list_projects(limit=1)`) in a worker thread, with a **10s timeout**. The result is **cached 60s on success, 15s on failure** (timeouts are cached too, so an outage doesn't start a new thread on every poll). An `asyncio.Lock` makes concurrent callers wait for one check and share its result.
  - Any check down → **HTTP 503 with the same JSON body**, so the UI can still show which piece failed.
  - In prod, details are reduced to `"connected"` / `"unavailable"` (no versions, project names or exception types).
- The db pool opens with `wait=False`, so the api starts even if the db is still booting; `/api/health` reports db down until it can connect.

## Security boundary
- **Only `/api/*` is proxied** through the web origin ([ADR 003](../decisions/003-web-proxies-only-api.md)). `/docs`, `/openapi.json`, `/livez` and `/dev/*` are unreachable through port 3000 (verified 404, including path-traversal attempts).
- Dev-only routes are **not registered at all** in prod, and the code default is `prod` ([ADR 005](../decisions/005-app-env-dev-prod-switch.md)).
- All published ports bind to `127.0.0.1`. The db is not published. Publicly, only `web` is reachable (through the Cloudflare Worker, see [deployment](../diagrams/deployment.md#public-demo-cloud-server)).
- `.dockerignore` keeps `.env`, `.git`, `web/`, `docs/` and data folders out of the api build context.
- The api container runs as non-root. **Known gap:** the web image still runs as root (deferred to the Block 9 production stage).

## Config and env mapping
Secrets live only in `.env` (gitignored); `.env.example` lists the names. Compose translates the owner's names to the standard names the SDKs read, so code never sees `PLACEWISE_*`:

| `.env` (owner) | Container env (api) | Notes |
|---|---|---|
| `APP_ENV` | `APP_ENV` | Compose default `dev`; **code default `prod`**; only `dev`/`prod` accepted |
| `APP_SECRET_KEY` | `APP_SECRET_KEY` | Required (compose fails fast if empty). `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | `DATABASE_URL=postgresql://placewise:${POSTGRES_PASSWORD}@db:5432/placewise` | Required. URL-safe chars only: `openssl rand -hex 24` |
| `PLACEWISE_ANTHROPIC_TEST_API_KEY` | `ANTHROPIC_API_KEY` | Not used in Block 0; Block 1's `seed` container uses it to write synthetic resumes |
| `PLACEWISE_VOYAGE_TEST_API_KEY` | `VOYAGE_API_KEY` | Not used yet in Block 0 |
| `PLACEWISE_LANGSMITH_TEST_API_KEY` | `LANGSMITH_API_KEY` | Used by the health check and tracing |
| `LANGSMITH_ENDPOINT`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` | same | Defaults: official endpoint, `true`, `placewise` |
| `DAILY_LLM_SPEND_CAP_USD` | same | Default 10; not enforced yet |

Settings are loaded by `pydantic-settings` (`src/placewise/config.py`); keys are `SecretStr` so they don't print in logs or reprs.

## How to run
```bash
cp .env.example .env          # then fill keys and generate the two secrets
docker compose up --build
open http://localhost:3000    # dashboard or login; System status is under Admin
```
- API docs (dev only): `http://localhost:8000/docs`
- Send a test trace (dev only): `curl -X POST http://localhost:8000/dev/trace` — a test trace reached the LangSmith project `placewise`.
- After changing web dependencies: `docker compose up --build -V web` (renews the anonymous `node_modules`/`.next` volumes).

## How to test
```bash
docker compose run --rm -T -v "$PWD/tests:/app/tests" --entrypoint pytest seed -q -p no:cacheprovider /app/tests
```
This runs the whole suite (126 tests as of Block 1) in the `seed` tools container, which uses the same image as the api. `docker compose exec api uv run pytest` doesn't work: the api image's `/opt/venv` isn't writable and the tests aren't mounted there.

**Block 0 has 23 tests, all passing** (QA verdict: PASS). They never touch the real db or LangSmith: `conftest.py` sets a fake env before import, and checks are mocked.

| File | Covers |
|---|---|
| `tests/test_api_routes.py` (12) | `/api/health` 200/503 paths, timeout handling, `/livez` touches nothing, dev vs prod routes, default `APP_ENV=prod`, invalid `APP_ENV` rejected, prod detail reduction (no leaks) |
| `tests/test_health_checks.py` (11) | `check_db` (OK, missing pgvector, error hides connection string, pool not open), LangSmith sync check (OK, missing key, error hides key), cache TTLs 60s/15s, timeout cached as failure, real timeout is 10s |
| `tests/conftest.py` | Safe env, app reload per `APP_ENV`, cache reset, check mocks |

**Live break-it (QA):** stop `db` → `/api/health` returns 503 in about 3s and the page still renders with Database "✕ Down"; restart `db` → recovers in about 5s.

## Failure modes
| Failure | What happens | Handling |
|---|---|---|
| db down or booting | `/api/health` 503, db "cannot connect (…)", ~3s response | Bounded pool wait (3s); api keeps running; auto-recovers when db returns |
| pgvector missing | 503, "connected, but the pgvector extension is not installed" | Init script creates it on first volume creation |
| LangSmith down / slow / bad key | 503, LangSmith down; result cached 15s | 10s timeout, cached failure, lock prevents thread pile-up; `/livez` unaffected |
| api down | Proxy returns a plain-text 500; the page shows "Can't reach the API. Is the api container running?" | UI catches the JSON parse failure |
| Missing `POSTGRES_PASSWORD` / `APP_SECRET_KEY` | `docker compose up` refuses to start | `${VAR:?…}` in compose |
| `APP_ENV` typo | api fails at startup (validation error) | `Literal["dev","prod"]` |

## Known limits
- Health response takes ~3s while the db is down (the pool wait). Acceptable for a status page.
- Proxy returns plain-text 500 (not JSON) when the api is down; the UI handles it.
- Web image runs as root and is a dev server; the production stage comes in Block 9.
- No schema or migrations yet (Block 2). Anthropic/Voyage keys and the spend cap are wired but unused.

## What later blocks add
- **Block 1–2:** synthetic data; migrations, the ingest graph, the `worker` service and the Postgres `SKIP LOCKED` queue.
- **Block 3:** the real portal (login, roles, session cookies) replaces the status page.
- **Block 8:** `n8n` and `mailpit` services.
- **Block 9:** ✅ production web build, public link through Cloudflare exposing only `web`, cloud server with auto-deploy (ADR 020). Still to do: non-root web image, Ops dashboard.
