# Sequence: System status (health check)

What happens when the System status page loads or the user clicks **Recheck**. Code: `web/src/app/system-status.tsx`, `web/next.config.ts`, `src/placewise/main.py`, `src/placewise/health.py`.

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant W as web (Next.js)
    participant A as api (FastAPI)
    participant C as LangSmith cache
    participant L as LangSmith
    participant D as db (Postgres)

    B->>W: GET /api/health (same origin)
    W->>A: rewrite to http://api:8000/api/health
    A->>C: check_langsmith() under asyncio.Lock
    alt cache fresh (60s if ok, 15s if failed)
        C-->>A: cached result
    else cache stale or empty
        A->>L: list_projects(limit=1) in a thread, 10s timeout
        L-->>A: ok, error, or timeout
        A->>C: store result with TTL
    end
    A->>D: SELECT extversion FROM pg_extension (3s pool wait)
    alt db up
        D-->>A: pgvector version
    else db down
        D--xA: error after about 3s
        Note over A: db reported as cannot connect
    end
    alt all checks ok
        A-->>W: 200 with checks JSON
    else any check down
        A-->>W: 503 with the same JSON body
    end
    W-->>B: response passed through
    Note over B: Shows each check as Connected or Down
```

## Key points
- **Cache:** the LangSmith call is slow and external, so it's cached (60s on success, 15s on failure, timeouts included). The lock means concurrent requests share one check instead of each starting a thread.
- **db-down path:** the pool waits at most 3s for a connection, then the check reports "cannot connect (<ExceptionType>)". The response is a 503 **with a body**, so the page still renders and marks Database as Down. QA measured recovery about 5s after restarting `db`.
- **api-down path (not shown):** the Next.js proxy returns a plain-text 500; the page can't parse it as JSON and shows "Can't reach the API. Is the api container running?"
- **Prod:** the same flow, but details are reduced to "connected"/"unavailable".
- **Not in this flow:** `/livez`, which Docker calls directly inside the api container and which checks nothing external.
