# 002: Everything runs in Docker Compose, including the database

- **Status:** accepted
- **Date:** 2026-10-22

## Context
The owner's machine already runs its own Postgres on port 5432 (Homebrew, without pgvector), and an old host `.venv` broke after a folder rename. The demo must start with one command and behave the same on any machine.

## Decision
All services run as containers defined in `docker-compose.yml`: `db`, `api`, `web` today; `worker`, `n8n`, `mailpit`, `tunnel` later. No host Python, Node or Postgres is used. Installs, tests and scripts run in containers, e.g.:
`docker compose run --rm -v "$PWD/tests:/app/tests" api pytest -q /app/tests`.
The db is **not** published to the host (no clash with the host's 5432); `127.0.0.1:5433` can be uncommented for debugging. Data lives in the named volume `db_data`.

## Alternatives considered
- **Host Postgres + host venv/node:** fastest edit loop, but it already failed twice here (missing pgvector, stale venv) and isn't reproducible for anyone else.
- **Managed cloud services (hosted Postgres, Vercel, etc.):** closer to production, but adds accounts, cost and network dependencies to a local demo.
- **Kubernetes (kind/minikube):** realistic for scale, far too heavy for one machine and one week.

## Tradeoffs and consequences
- **Gain:** one-command startup, pinned versions (pgvector 0.8.1, Python 3.12, Node 22, Next 16.4.2), no conflict with host software, same environment for every role and agent.
- **Give up:** slower file watching on macOS (needs `WATCHPACK_POLLING=true`), anonymous volumes for `node_modules`/`.next` that must be renewed with `-V` after dependency changes, and dev-mode images (reload, dev server) that are not production images yet.
- **Revisit if:** the app is deployed for real; then we'd add production build stages (Block 9) and likely move the db to a managed service.
