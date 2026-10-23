# Build Log

Real problems hit during the build only: symptom → cause → fix. Newest first.

## 2026-10-22 (Block 0)
- **LangSmith cache tests broke when the clock was patched globally.** Patching `time.monotonic` globally to fake the passage of time also froze the asyncio event loop's clock, which broke `asyncio.wait_for`. *Fix:* patch only `health.py`'s own `time` (`monkeypatch.setattr(health, "time", SimpleNamespace(monotonic=clock))`), leaving asyncio's clock alone.
- **Reviewer findings (verdict: APPROVE WITH FIXES).** The web proxy forwarded more than `/api/*`, exposing API docs and dev routes through the web origin; `.env.example` was missing variables; there was no `.dockerignore`; a named `node_modules` volume went stale after dependency changes; the Docker healthcheck hit `/docs` (dev-only); there were no tests. *Fix:* rewrite only `/api/*`; filled `.env.example`; added `.dockerignore`; switched to anonymous volumes for `node_modules`/`.next`; added `/livez` for the healthcheck; added 23 tests. *Deferred:* the web image still runs as root, to be fixed in the Block 9 production stage.
- **QA notes (verdict: PASS).** With the db stopped, `/api/health` takes about 3s to answer (the pool wait) before returning 503; when the api is down, the Next.js proxy returns a plain-text 500 instead of JSON. Both accepted as known limits: the page still renders and shows which service is down.
- **Role agents not found when launched by name.** `Agent type 'reviewer' not found`. *Cause:* Claude Code loads `.claude/agents/` from the directory where the session started, and this session started in the parent folder. *Fix:* run each role as a general-purpose agent that reads its instructions from `.claude/agents/<role>.md`. Sessions started inside the repo load the roles natively.
- **LangSmith SDK deprecation:** `list_runs()` warns that it will be removed after Jan 31, 2027 and points to `client.runs.query()`. *Fix:* use the new query API in evals and tests. `/api/health` uses `list_projects()`, which shows no warning.
- **Next.js 16 breaking changes.** The scaffold's `web/AGENTS.md` warns that APIs differ from older versions. *Fix:* checked the docs bundled in `node_modules/next/dist/docs/` before writing config. `rewrites()` is unchanged, so the `/api/*` proxy works as designed.
- **`.env.example` deleted by a commit.** The owner had renamed `.env.example` to `.env`, and a chained `git add .env.example` then staged the deletion. *Fix:* restored it in the next commit. No secrets were exposed because `.env` is gitignored. *Lesson:* check that files exist before staging them in chained commands.

## 2026-10-22 (setup)
- **pgvector extension missing in local Postgres.** `pg_available_extensions` had no `vector` row. *Cause:* Homebrew Postgres 17 ships without pgvector. *Fix:* `brew install pgvector`. The Docker setup uses the `pgvector/pgvector` image, so this only matters outside Docker.
- **Project folder renamed** (`aec-recruiter-copilot` → `placewise`). *Effect:* the existing `.venv` holds absolute paths and is stale. *Fix:* rebuild with `uv sync`, or run in Docker.
