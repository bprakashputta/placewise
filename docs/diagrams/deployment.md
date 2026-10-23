# Deployment (Docker Compose)

Everything runs in containers on one machine ([ADR 002](../decisions/002-everything-in-docker-compose.md)). Compose project name: `placewise`. No custom networks are defined, so all services share the default network `placewise_default` and reach each other by service name (`db`, `api`, `web`).

```mermaid
flowchart TB
    subgraph host["Host machine (127.0.0.1 only)"]
        p3000["127.0.0.1:3000"]
        p8000["127.0.0.1:8000<br/>local only, API docs in dev"]
    end

    subgraph net["Docker network: placewise_default"]
        web["web :3000<br/>node:22-alpine"]
        api["api :8000<br/>uv python3.12, user app"]
        db[("db :5432<br/>pgvector 0.8.1-pg17<br/>not published")]
    end

    vol_db[("named volume<br/>db_data")]
    vol_web["anonymous volumes<br/>/app/node_modules, /app/.next"]
    bind_src["bind mount ./src to /app/src"]
    bind_web["bind mount ./web to /app"]

    p3000 --> web
    p8000 --> api
    web -->|"http://api:8000/api/*"| api
    api -->|"postgresql://db:5432"| db
    db --- vol_db
    web --- vol_web
    web --- bind_web
    api --- bind_src
```

## Services
| Service | Container port | Host port | Volumes | Starts after | Healthcheck |
|---|---|---|---|---|---|
| `db` | 5432 | **none** (host Postgres owns 5432; optional `127.0.0.1:5433` for debugging) | `db_data` → `/var/lib/postgresql/data`; `./docker/db/init` → `/docker-entrypoint-initdb.d` (ro) | — | `pg_isready` every 5s |
| `api` | 8000 | `127.0.0.1:8000` | `./src` → `/app/src` (dev reload) | `db` healthy | `GET /livez` every 10s (image `HEALTHCHECK`) |
| `web` | 3000 | `127.0.0.1:3000` | `./web` → `/app`; anonymous `/app/node_modules`, `/app/.next` | `api` started | none |

All services use `restart: unless-stopped`.

## Notes
- The api's virtualenv lives in `/opt/venv`, outside `/app/src`, so mounting `./src` for reload doesn't hide installed packages.
- The anonymous volumes keep the image's `node_modules` and `.next` from being hidden by the `./web` bind mount. After changing web dependencies: `docker compose up --build -V web`.
- `WATCHPACK_POLLING=true` makes file watching reliable through Docker on macOS.

## What becomes public later
Today nothing is public: every published port binds to `127.0.0.1`.
When the optional **tunnel** is added (Block 9, **Planned**), it will expose **only `web`**. The api stays reachable only through web's `/api/*` proxy, and the db stays internal.

| Port | Now | Later (with tunnel) |
|---|---|---|
| web 3000 | localhost | **public via tunnel** |
| api 8000 | localhost (dev docs) | localhost only / internal |
| db 5432 | internal only | internal only |
