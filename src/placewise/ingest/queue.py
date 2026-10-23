"""Postgres-backed job queue for ingest.

- enqueue: idempotent per (source, source_ref), so re-submitting the same item does nothing.
- claim: FOR UPDATE SKIP LOCKED, so concurrent workers never take the same job.
- fail: bounded retries with exponential backoff, then 'failed' with the error kept.
- reclaim_stale: jobs left 'running' by a crashed worker go back to the queue.
"""
from __future__ import annotations

import json

from psycopg import AsyncConnection
from psycopg.rows import dict_row

RETRY_BASE_S = 20
STALE_AFTER_MIN = 10


async def enqueue(conn: AsyncConnection, source: str, source_ref: str, payload: dict) -> int | None:
    cur = await conn.execute(
        """INSERT INTO ingest_jobs (source, source_ref, payload) VALUES (%s, %s, %s)
           ON CONFLICT (source, source_ref) DO NOTHING RETURNING id""",
        (source, source_ref, json.dumps(payload)))
    row = await cur.fetchone()
    return row[0] if row else None


async def claim(conn: AsyncConnection, worker_id: str) -> dict | None:
    cur = conn.cursor(row_factory=dict_row)
    await cur.execute(
        """UPDATE ingest_jobs SET status = 'running', locked_by = %s, locked_at = now(),
                  attempts = attempts + 1, updated_at = now()
           WHERE id = (SELECT id FROM ingest_jobs
                       WHERE status = 'queued' AND not_before <= now()
                       ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)
           RETURNING *""", (worker_id,))
    return await cur.fetchone()


async def finish(conn: AsyncConnection, job_id: int, status: str, result: dict | None = None,
                 resume_file_id: int | None = None, error: str | None = None, worker: str | None = None) -> bool:
    """Only the worker that holds the lock may finish the job (a reclaimed job's late finisher can't
    overwrite the new owner's result). Returns False if the lock was lost."""
    cur = await conn.execute(
        """UPDATE ingest_jobs SET status = %s, result = %s, resume_file_id = COALESCE(%s, resume_file_id),
                  error = %s, locked_by = NULL, locked_at = NULL, updated_at = now()
           WHERE id = %s AND (%s::text IS NULL OR locked_by = %s)""",
        (status, json.dumps(result) if result is not None else None, resume_file_id, error, job_id, worker, worker))
    return cur.rowcount == 1


async def fail(conn: AsyncConnection, job: dict, error: str, worker: str | None = None) -> str:
    """Retry later with backoff, or give up after max_attempts. Returns the new status ('lost' if the
    job was reclaimed by someone else meanwhile)."""
    if job["attempts"] < job["max_attempts"]:
        delay = RETRY_BASE_S * 2 ** (job["attempts"] - 1)
        cur = await conn.execute(
            """UPDATE ingest_jobs SET status = 'queued', not_before = now() + make_interval(secs => %s),
                      error = %s, locked_by = NULL, locked_at = NULL, updated_at = now()
               WHERE id = %s AND (%s::text IS NULL OR locked_by = %s)""",
            (delay, error[:2000], job["id"], worker, worker))
        return "queued" if cur.rowcount == 1 else "lost"
    ok = await finish(conn, job["id"], "failed", error=error[:2000], worker=worker)
    return "failed" if ok else "lost"


async def reclaim_stale(conn: AsyncConnection) -> int:
    """Requeue jobs whose worker vanished. A job that has used all its attempts (e.g. a file that
    crashes the worker every time) is marked failed instead of looping forever."""
    cur = await conn.execute(
        """UPDATE ingest_jobs
           SET status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
               error = CASE WHEN attempts >= max_attempts
                            THEN 'worker stopped responding on every attempt (possible crash on this file)'
                            ELSE error END,
               locked_by = NULL, locked_at = NULL, updated_at = now()
           WHERE status = 'running' AND locked_at < now() - make_interval(mins => %s)""", (STALE_AFTER_MIN,))
    return cur.rowcount


async def summary(conn: AsyncConnection) -> dict:
    cur = await conn.execute("SELECT status, count(*) FROM ingest_jobs GROUP BY status")
    return {status: n for status, n in await cur.fetchall()}


async def defer(conn: AsyncConnection, job: dict, minutes: int, reason: str, worker: str | None = None) -> None:
    """Pause a job without using up an attempt (e.g. the daily spend cap is reached)."""
    await conn.execute(
        """UPDATE ingest_jobs SET status = 'queued', attempts = GREATEST(attempts - 1, 0),
                  not_before = now() + make_interval(mins => %s), error = %s,
                  locked_by = NULL, locked_at = NULL, updated_at = now()
           WHERE id = %s AND (%s::text IS NULL OR locked_by = %s)""",
        (minutes, reason, job["id"], worker, worker))
