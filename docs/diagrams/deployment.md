# Deployment (Docker Compose)

Everything runs in containers on one machine ([ADR 002](../decisions/002-everything-in-docker-compose.md)). Compose project name: `placewise`. No custom networks are defined, so all services share the default network `placewise_default` and reach each other by service name (`db`, `api`, `web`).

![Docker Compose deployment: host ports, services on placewise_default, named volumes, on-demand seed container](deployment.svg)

*Services, ports and volumes. Source: [`src/deployment.d2`](src/deployment.d2).*

## Services
| Service | Container port | Host port | Volumes | Starts after | Healthcheck |
|---|---|---|---|---|---|
| `db` | 5432 | **none** (host Postgres owns 5432; optional `127.0.0.1:5433` for debugging) | `db_data` → `/var/lib/postgresql/data`; `./docker/db/init` → `/docker-entrypoint-initdb.d` (ro) | — | `pg_isready` every 5s |
| `api` | 8000 | `127.0.0.1:8000` | `./src` → `/app/src` (dev reload); `storage` → `/app/storage`; read-only: `./prompts`, `./data/seed/public`, `./data/seed/resumes`, `./outputs/samples` (never `data/seed/truth`) | `db` healthy | `GET /livez` every 10s (image `HEALTHCHECK`) |
| `worker` | none (no HTTP) | none | `./src`; `storage` → `/app/storage`; read-only: `./prompts`, `./data/seed/resumes` (never `data/seed/truth`) | `db` healthy | disabled (it serves no HTTP) |
| `seed` | — | none | `./src`, `./data` (incl. `seed/truth`), `./outputs`; `./prompts` read-only | on demand (`docker compose run --rm seed …`, profile `tools`) | n/a (one-shot) |
| `web` | 3000 | `127.0.0.1:3000` | `./web` → `/app`; anonymous `/app/node_modules`, `/app/.next` | `api` started | none |

All long-running services use `restart: unless-stopped`.

## Worker notes
- Same image as the api (`docker/api.Dockerfile`), started with `python -m placewise.worker`.
- Scale out with `docker compose up -d --scale worker=3`. Each process runs `WORKER_CONCURRENCY` jobs at once (default 4).
- `stop_grace_period: 60s`: on SIGTERM a worker stops claiming and finishes in-flight jobs. Anything cut off is reclaimed by another worker after 10 minutes.
- Both the api and the worker run migrations at startup; an advisory lock makes that safe when several start together.

## Notes
- The api's virtualenv lives in `/opt/venv`, outside `/app/src`, so mounting `./src` for reload doesn't hide installed packages.
- The image creates `/app/storage/uploads` owned by the non-root `app` user **before** the named volume is mounted, so a fresh `storage` volume inherits that ownership. (Uploads failed when it was root-owned; reviewer blocker fixed in `8fc541e`.)
- Prompts are copied into the image and also bind-mounted in dev. A changed bind mount needs a container **recreate** (`docker compose up -d`), not a restart.
- The anonymous volumes keep the image's `node_modules` and `.next` from being hidden by the `./web` bind mount. After changing web dependencies: `docker compose up --build -V web`.
- `WATCHPACK_POLLING=true` makes file watching reliable through Docker on macOS.

## What becomes public later
Today nothing is public: every published port binds to `127.0.0.1`.
When the optional **tunnel** is added (Block 9, **Planned**), it will expose **only `web`**. The api stays reachable only through web's `/api/*` proxy, and the db stays internal. Auth (Block 3) must be in place first.

| Port | Now | Later (with tunnel) |
|---|---|---|
| web 3000 | localhost | **public via tunnel** |
| api 8000 | localhost (dev docs) | localhost only / internal |
| db 5432 | internal only | internal only |
