# 010: Postgres job queue with SKIP LOCKED instead of Redis/Celery

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Ingest is slow (an LLM call plus embeddings per resume, ~seconds to a minute) and must not run inside an API request. We need background jobs that survive restarts, never process the same resume twice at the same time, retry with limits, and scale by adding workers. The stack already has one Postgres ([ADR 001](001-postgres-pgvector-single-store.md)), and everything runs in Docker Compose on one machine.

## Decision
A plain `ingest_jobs` table in the same Postgres, used as a queue (`src/placewise/ingest/queue.py`):
- **claim:** `UPDATE … WHERE id = (SELECT id … WHERE status = 'queued' AND not_before <= now() ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)`, so concurrent workers never take the same job.
- **enqueue:** unique `(source, source_ref)` with `ON CONFLICT DO NOTHING`, so re-submitting is a no-op.
- **retries:** backoff 20 s, 40 s; `failed` after 3 attempts with the error kept.
- **lock ownership:** `finish`, `fail` and `defer` only apply if `locked_by` is still the caller.
- **stale reclaim:** jobs `running` for more than 10 minutes go back to the queue (or to `failed` if out of attempts); the job timeout (8 minutes) stays below that window.
- **defer:** the spend cap pauses a job for 30 minutes without using an attempt.
- Workers are a separate container: `docker compose up -d --scale worker=3`, 4 async slots each.

## Alternatives considered
- **Redis + Celery / RQ / Arq:** mature, but adds a broker container, a second source of truth (job state in Redis, results in Postgres) and no transaction across "job done" and "profile stored".
- **A managed queue (SQS, Cloud Tasks):** not local; breaks "everything runs in Docker".
- **FastAPI BackgroundTasks:** dies with the api process, no retries, no scaling.
- **pgmq / procrastinate / other Postgres queue libraries:** viable, but the needed behavior is ~90 lines of SQL that are easy to read and explain.

## Tradeoffs and consequences
- **Gain:** one database, job state queryable with SQL (`/api/ingest/summary`), easy to explain, transactional with the data. 24 DB integration tests cover concurrent claims, backoff, defer, reclaim and lock ownership.
- **Give up:** polling (idle slots sleep 2 s), no priorities or fan-out routing, and Postgres carries the queue load. Fine for hundreds to thousands of resumes; a firm ingesting millions per day would want a dedicated broker.
- **Revisit if:** queue throughput limits ingest, or we need scheduling, priorities or cross-service events beyond what n8n (Block 8) provides.
