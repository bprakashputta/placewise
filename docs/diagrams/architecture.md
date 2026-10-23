# Architecture

Containers and data flow. **Solid boxes are built (Block 0). Dashed boxes marked "PLANNED" do not exist yet.**

```mermaid
flowchart LR
    browser["Browser"]

    subgraph compose["Docker Compose: project placewise"]
        web["web<br/>Next.js 16 dev server<br/>:3000"]
        api["api<br/>FastAPI, Python 3.12<br/>:8000"]
        db[("db<br/>Postgres 17 + pgvector")]
        worker["worker<br/>LangGraph jobs<br/>PLANNED, Block 2"]
        n8n["n8n<br/>triggers and integrations<br/>PLANNED, Block 8"]
        mailpit["mailpit<br/>local test inbox<br/>PLANNED, Block 8"]
        tunnel["tunnel<br/>Cloudflare quick tunnel<br/>PLANNED, Block 9"]
    end

    langsmith["LangSmith<br/>external SaaS"]

    browser -->|"pages + /api/*"| web
    web -->|"rewrite /api/* only"| api
    api -->|"SQL, pgvector check"| db
    api -->|"health check + traces"| langsmith

    tunnel -.->|"public link"| web
    worker -.-> db
    n8n -.->|"/api/*"| api
    n8n -.-> mailpit

    classDef planned stroke-dasharray: 5 5,fill:#f5f5f5,color:#666
    class worker,n8n,mailpit,tunnel planned
```

## What exists now (Block 0)
| Container | Role |
|---|---|
| `web` | The only thing the browser talks to. Proxies **only** `/api/*` to the api ([ADR 003](../decisions/003-web-proxies-only-api.md)). |
| `api` | Stateless FastAPI. `/api/health` (readiness), `/livez` (liveness), dev-only `/docs` and `/dev/trace`. |
| `db` | The single data store ([ADR 001](../decisions/001-postgres-pgvector-single-store.md)). |
| LangSmith | External tracing service; checked by `/api/health`. |

## Planned (not built)
- **worker** (Block 2): runs LangGraph jobs from a Postgres `SKIP LOCKED` queue.
- **n8n**, **mailpit** (Block 8): intake triggers, notifications, approved-outreach sending to a local inbox.
- **tunnel** (Block 9, optional): temporary public link to `web` only.

See also: [deployment](deployment.md) · [health-check sequence](sequence-health-check.md) · [Foundation module](../modules/foundation.md)
