"""Ingest API: queue status for everyone; bulk seed import in dev only.
(File upload is added in step D, once the full pipeline exists.)"""
from fastapi import APIRouter, HTTPException
from psycopg.rows import dict_row

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
