# Architecture

Containers and data flow as of Block 2. Solid boxes are built. Dashed boxes are **planned** and don't exist yet.

![Placewise architecture: users, Docker Compose services, data, external AI services, dev tools](architecture.svg)

*Containers and data flow (blue = Placewise services, green = data, orange = external AI). Source: [`src/architecture.d2`](src/architecture.d2).*

## What exists now
| Container | Role |
|---|---|
| `web` | The only thing the browser talks to. Proxies **only** `/api/*` to the api ([ADR 003](../decisions/003-web-proxies-only-api.md)). Pages: System status (`/`) and the dev-only Seed page (`/seed`). The portal shell (Block 3) is being built on its own branch. |
| `api` | Stateless FastAPI. `/api/health` (readiness), `/livez` (liveness), the candidates API (list, filters, detail, file view/download, **upload**) and ingest queue status/retry. Dev only: `/docs`, `/dev/trace`, `/api/dev/seed/*`, `/api/dev/ingest/*`. Saves uploads to the `storage` volume and enqueues a job; it never runs the pipeline itself. |
| `worker` | Runs the LangGraph ingest pipeline ([Ingest module](../modules/ingest.md)). Claims jobs from the Postgres queue with `FOR UPDATE SKIP LOCKED` ([ADR 010](../decisions/010-postgres-job-queue-skip-locked.md)); 3 containers × 4 job slots in the full ingest run. Reads uploads from `storage` and seed files from `data/seed/resumes` (read-only). The answer key is **not mounted**. |
| `db` | The single data store ([ADR 001](../decisions/001-postgres-pgvector-single-store.md)): people, resume files, profiles, section chunks (pgvector HNSW + full-text), the job queue, the extraction cache and the LLM cost log. See the [data model](data-model.svg). |
| `seed` | On-demand tools container (`profiles: ["tools"]`). Generates synthetic data (Block 1) and runs the evals. The only container that mounts `data/seed/truth` ([ADR 008](../decisions/008-answer-key-isolation.md)). |
| Anthropic | Claude Sonnet 5.5 for profile extraction (worker); Claude Haiku 5.5 for synthetic data (seed). |
| Voyage AI | `voyage-4-large` embeddings, 1024 dimensions (worker). |
| LangSmith | Tracing (one trace per resume), checked by `/api/health`. |

## Mounts
| Host path / volume | `api` | `worker` | `seed` |
|---|---|---|---|
| `./src`, `./prompts` (ro) | yes (dev reload) | yes | yes |
| `./data/seed/resumes` | read-only | read-only | read/write (via `./data`) |
| `./data/seed/public`, `./outputs/samples` | read-only | no | read/write |
| `./data/seed/truth` (answer key) | **no** | **no** | read/write |
| `storage` named volume (uploads) | read/write | read/write | no |

Prompts are also baked into the image (`COPY prompts`), so a container without the bind mount still has them.

## Planned (not built)
- **n8n**, **mailpit** (Block 8): resume intake from an Apply page, email and job boards; approved outreach sent to a local inbox.
- **tunnel** (Block 9, optional): temporary public link to `web` only.
- **Auth** (Block 3): every candidate and ingest route will require a session.

See also: [deployment](deployment.md) · [ingest graph](ingest-graph.svg) · [queue lifecycle](queue-lifecycle.svg) · [data model](data-model.svg) · [health-check sequence](sequence-health-check.md) · [seed pipeline sequence](sequence-seed-pipeline.md)
