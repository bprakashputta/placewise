# Placewise

An AI layer for A/E/C (Architecture, Engineering & Construction) recruiting. It turns resumes and messy job notes into evidence-backed shortlists, submittals and outreach. It sits on top of your ATS and doesn't replace it.

> 🚧 Work in progress. See [`docs/PLAN.md`](docs/PLAN.md) for build status and [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) for scope.

**Stack:** Next.js · FastAPI · LangChain · LangGraph · LangSmith · Claude · Voyage AI · Postgres + pgvector · n8n · Docker Compose

## Current status: Block 1 (Synthetic data)
- **Block 0 (Foundation):** three containers start with one command and a **System status** page shows whether the API, the database (with pgvector) and LangSmith are connected. Details: [`docs/modules/foundation.md`](docs/modules/foundation.md).
- **Block 1 (Synthetic data):** a fully fake A/E/C candidate pool with a known answer key: **597 resumes** (349 PDF, 190 DOCX, 58 TXT, including image-only, corrupt, hidden-injection and duplicate files), **15 job orders** with messy recruiter notes, and a relevance key (strong / partial / none, with a reason per requirement). Code generates the facts, Claude Haiku 5.5 writes structured resumes that must pass fact checks (597/597 pass), and code renders them with five templates. A dev-only **Seed page** shows progress, stats and dev-split samples. Details: [`docs/modules/synthetic-data.md`](docs/modules/synthetic-data.md).

No recruiting features yet; those start with Block 2 (ingest).

## Quick start
Needs only Docker Desktop and git. Everything (db included) runs in containers.

```bash
cp .env.example .env
# Fill in .env:
#   APP_SECRET_KEY     → openssl rand -hex 32
#   POSTGRES_PASSWORD  → openssl rand -hex 24   (URL-safe characters only)
#   PLACEWISE_LANGSMITH_TEST_API_KEY
#   PLACEWISE_ANTHROPIC_TEST_API_KEY (seed data generation; Voyage key used from Block 2)
docker compose up --build
```

Open **http://localhost:3000**. You should see "All systems operational".

| URL | What |
|---|---|
| http://localhost:3000 | Web portal (System status page for now) |
| http://localhost:3000/seed | Seed page: synthetic data progress, stats, sample resumes (only when `APP_ENV=dev`) |
| http://localhost:8000/docs | API docs (only when `APP_ENV=dev`, local only) |

All ports bind to `127.0.0.1`. The database isn't published to the host.

## Synthetic data (seed CLI)
Runs in the on-demand `seed` tools container. `write`, `samples` and `job-orders` call Claude Haiku 5.5 and need `PLACEWISE_ANTHROPIC_TEST_API_KEY` (a full run costs under $1).

```bash
docker compose run --rm seed facts --count 500 --seed 42   # candidate facts (ground truth), no LLM
docker compose run --rm seed samples                       # one PDF per template → outputs/samples/
docker compose run --rm seed write                         # LLM writes + fact-checks resumes (--limit, --ids, --force)
docker compose run --rm seed render                        # code noise + PDF/DOCX/TXT files
docker compose run --rm seed job-orders                    # job orders, targeted candidates, notes, answer key
docker compose run --rm seed write && docker compose run --rm seed render   # the targeted candidates' resumes
```
The answer key in `data/seed/truth/` is mounted only into the `seed` container, never into the api.

## Run the tests
```bash
docker compose run --rm -T -v "$PWD/tests:/app/tests" --entrypoint pytest seed -q -p no:cacheprovider /app/tests
```
126 tests (23 Block 0 + 103 Block 1); they never touch the real database, LangSmith or the Anthropic API. (`docker compose exec api uv run pytest` doesn't work: the api image's `/opt/venv` isn't writable and the tests aren't mounted there.)

## Docs
- [Architecture](docs/diagrams/architecture.md) · [Deployment](docs/diagrams/deployment.md) · [Health-check sequence](docs/diagrams/sequence-health-check.md) · [Seed pipeline sequence](docs/diagrams/sequence-seed-pipeline.md)
- [Foundation module](docs/modules/foundation.md) · [Synthetic data module](docs/modules/synthetic-data.md)
- [Decisions (ADRs)](docs/decisions/)
- [Build log](docs/build-log.md): real problems hit and how they were fixed

**For agents/contributors:** start with [`AGENTS.md`](AGENTS.md).
