"""Ingest API: queue status and retry for everyone (auth in Block 3); bulk seed import and reset in dev only.
File upload lives in candidates_api.py."""
from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row

from .auth import require_admin
from .db import pool
from .ingest import queue
from .ingest.sources import SEED_RESUMES

router = APIRouter(prefix="/api/ingest", tags=["ingest"])
dev_router = APIRouter(prefix="/api/dev/ingest", tags=["dev: ingest"])


@router.get("/summary")
async def summary() -> dict:
    async with pool().connection() as conn:
        return {"jobs": await queue.summary(conn)}


@router.get("/jobs")
async def jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    limit = max(1, min(limit, 500))
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """SELECT id, source, source_ref, status, attempts, error, result, resume_file_id, created_at, updated_at
               FROM ingest_jobs WHERE (%s::text IS NULL OR status = %s) ORDER BY id DESC LIMIT %s""",
            (status, status, limit))
        return await cur.fetchall()


@router.get("/jobs/{job_id}")
async def job(job_id: int) -> dict:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT * FROM ingest_jobs WHERE id = %s", (job_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "job not found")
    return row


@dev_router.post("/seed")
async def enqueue_seed(limit: int = 0, folders: str = "") -> dict:
    """Queue the synthetic resumes for ingest (idempotent: already-queued folders are skipped)."""
    wanted = [f for f in folders.split(",") if f] or sorted(p.name for p in SEED_RESUMES.iterdir() if p.is_dir())
    if limit:
        wanted = wanted[:limit]
    added = 0
    async with pool().connection() as conn:
        for folder in wanted:
            if await queue.enqueue(conn, "seed", folder, {"folder": folder}):
                added += 1
    return {"requested": len(wanted), "queued": added, "already_queued": len(wanted) - added}


@router.post("/jobs/retry-failed", dependencies=[Depends(require_admin)])
async def retry_failed() -> dict:
    """Put failed jobs back in the queue (e.g. after fixing a configuration problem)."""
    async with pool().connection() as conn:
        cur = await conn.execute(
            """UPDATE ingest_jobs SET status = 'queued', attempts = 0, not_before = now(), error = NULL,
                      updated_at = now() WHERE status = 'failed'""")
        return {"requeued": cur.rowcount}


@dev_router.post("/reset")
async def reset_ingested(confirm: str = "") -> dict:
    """Dev only: delete ingested people/files/profiles/chunks/jobs so everything can be re-ingested.
    Keeps extraction_cache and llm_calls, so a re-ingest costs no LLM spend."""
    if confirm != "yes":
        raise HTTPException(400, "pass confirm=yes")
    async with pool().connection() as conn:
        await conn.execute("TRUNCATE chunks, profiles, ingest_jobs, resume_files, people RESTART IDENTITY CASCADE")
    return {"reset": True}
