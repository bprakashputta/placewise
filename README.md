# Placewise

An AI layer for A/E/C (Architecture, Engineering & Construction) recruiting. It turns resumes and messy job notes into evidence-backed shortlists, submittals and outreach. It sits on top of your ATS and doesn't replace it.

> 🚧 Work in progress. See [`docs/PLAN.md`](docs/PLAN.md) for build status and [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) for scope.

**Stack:** Next.js · FastAPI · LangChain · LangGraph · LangSmith · Claude · Voyage AI · Postgres + pgvector · n8n · Docker Compose

## Current status: Block 0 (Foundation)
Three containers start with one command and a **System status** page shows whether the API, the database (with pgvector) and LangSmith are connected. No recruiting features yet. Details: [`docs/modules/foundation.md`](docs/modules/foundation.md).

## Quick start
Needs only Docker Desktop and git. Everything (db included) runs in containers.

```bash
cp .env.example .env
# Fill in .env:
#   APP_SECRET_KEY     → openssl rand -hex 32
#   POSTGRES_PASSWORD  → openssl rand -hex 24   (URL-safe characters only)
#   PLACEWISE_LANGSMITH_TEST_API_KEY (plus the Anthropic and Voyage keys, used from Block 2)
docker compose up --build
```

Open **http://localhost:3000**. You should see "All systems operational".

| URL | What |
|---|---|
| http://localhost:3000 | Web portal (System status page for now) |
| http://localhost:8000/docs | API docs (only when `APP_ENV=dev`, local only) |

All ports bind to `127.0.0.1`. The database isn't published to the host.

## Run the tests
```bash
docker compose run --rm -v "$PWD/tests:/app/tests" api pytest -q /app/tests
```
23 tests; they never touch the real database or LangSmith.

## Docs
- [Architecture](docs/diagrams/architecture.md) · [Deployment](docs/diagrams/deployment.md) · [Health-check sequence](docs/diagrams/sequence-health-check.md)
- [Foundation module](docs/modules/foundation.md)
- [Decisions (ADRs)](docs/decisions/)
- [Build log](docs/build-log.md): real problems hit and how they were fixed

**For agents/contributors:** start with [`AGENTS.md`](AGENTS.md).
