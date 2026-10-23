# Build Log

Real problems hit during the build only: symptom → cause → fix. Newest first.

## 2026-10-22
- **pgvector extension missing in local Postgres.** `pg_available_extensions` had no `vector` row. *Cause:* Homebrew Postgres 17 ships without pgvector. *Fix:* `brew install pgvector`. The Docker setup uses the `pgvector/pgvector` image, so this only matters outside Docker.
- **Project folder renamed** (`aec-recruiter-copilot` → `placewise`). *Effect:* the existing `.venv` holds absolute paths and is stale. *Fix:* rebuild with `uv sync`, or run in Docker.
