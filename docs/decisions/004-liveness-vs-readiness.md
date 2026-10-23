# 004: Separate liveness (/livez) from readiness (/api/health)

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Docker needs to know whether the api process is alive. Users (and the System status page) need to know whether the api's dependencies (db with pgvector, LangSmith) are reachable. The first version pointed the Docker healthcheck at `/docs`, which the reviewer flagged: it only exists in dev and says nothing useful.

## Decision
- **`/livez`** (liveness): returns `{"ok": true}` and touches nothing external. Used by the api image's `HEALTHCHECK` every 10s. Not under `/api`, so not proxied.
- **`/api/health`** (readiness): checks api, db (+ pgvector) and LangSmith. Returns 200 if all are OK, otherwise **503 with the same JSON body** so the UI can show which piece is down. The LangSmith call has a 10s timeout, is cached (60s ok / 15s failure) and runs behind an `asyncio.Lock`. In prod, details are reduced to "connected"/"unavailable".

## Alternatives considered
- **One `/health` for both:** a LangSmith or db outage would mark the api container unhealthy, and restart policies or orchestrators could restart a healthy process in a loop over a problem it can't fix.
- **Healthcheck on `/docs`:** missing in prod, and checks nothing.
- **No caching of the LangSmith check:** every poll would make an external call; during an outage, each poll would start a new thread waiting on a timeout.

## Tradeoffs and consequences
- **Gain:** container health reflects the process only; dependency problems are visible but don't trigger restarts; polling is cheap.
- **Give up:** LangSmith status can be up to 60s stale; while the db is down, `/api/health` takes about 3s (the pool wait) to answer.
- **Revisit if:** an orchestrator needs a readiness probe to route traffic (then `/api/health`, or a lighter internal variant, becomes the readiness probe).
