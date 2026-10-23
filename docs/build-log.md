# Build Log

Real problems hit during the build only: symptom → cause → fix. Newest first.

## 2026-10-22 (Block 0)
- **Role agents not found when launched by name.** `Agent type 'reviewer' not found`. *Cause:* Claude Code loads `.claude/agents/` from the directory where the session started, and this session started in the parent folder. *Fix:* run each role as a general-purpose agent that reads its instructions from `.claude/agents/<role>.md`. Sessions started inside the repo load the roles natively.
- **LangSmith SDK deprecation:** `list_runs()` warns that it will be removed after Jan 31, 2027 and points to `client.runs.query()`. *Fix:* use the new query API in evals and tests. `/health` uses `list_projects()`, which shows no warning.
- **Next.js 16 breaking changes.** The scaffold's `web/AGENTS.md` warns that APIs differ from older versions. *Fix:* checked the docs bundled in `node_modules/next/dist/docs/` before writing config. `rewrites()` is unchanged, so the `/api/*` proxy works as designed.
- **`.env.example` deleted by a commit.** The owner had renamed `.env.example` to `.env`, and a chained `git add .env.example` then staged the deletion. *Fix:* restored it in the next commit. No secrets were exposed because `.env` is gitignored. *Lesson:* check that files exist before staging them in chained commands.

## 2026-10-22 (setup)
- **pgvector extension missing in local Postgres.** `pg_available_extensions` had no `vector` row. *Cause:* Homebrew Postgres 17 ships without pgvector. *Fix:* `brew install pgvector`. The Docker setup uses the `pgvector/pgvector` image, so this only matters outside Docker.
- **Project folder renamed** (`aec-recruiter-copilot` → `placewise`). *Effect:* the existing `.venv` holds absolute paths and is stale. *Fix:* rebuild with `uv sync`, or run in Docker.
