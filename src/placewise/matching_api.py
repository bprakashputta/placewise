"""Job orders + matching API (Blocks 4 + 6). Requires a signed-in user."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from .auth import current_user
from .db import pool
from .ingest.spend import SpendCapReached
from .matching.engine import STALE_RUN_MIN, RunInProgress, extract_job, run_match

router = APIRouter(prefix="/api", tags=["job orders"])
dev_router = APIRouter(prefix="/api/dev/job-orders", tags=["dev: job orders"])
PUBLIC = Path("/app/data/seed/public")


class NewJobOrder(BaseModel):
    notes: str = Field(min_length=20, max_length=6000)


async def _create(notes: str, user_id: int | None, source_ref: str | None = None) -> dict:
    spec, cost = await extract_job(notes)
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """INSERT INTO job_orders (title, client, raw_notes, spec, source_ref, created_by)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (source_ref) DO NOTHING
               RETURNING id, title, client, raw_notes, spec, status, created_at""",
            (spec.title, spec.client, notes, spec.model_dump_json(), source_ref, user_id))
        row = await cur.fetchone()
    return {**(row or {}), "cost_usd": round(cost, 5)}


@router.post("/job-orders")
async def create_job_order(body: NewJobOrder, user: dict = Depends(current_user)) -> dict:
    try:
        return await _create(body.notes.strip(), user["id"])
    except SpendCapReached as e:
        raise HTTPException(429, str(e))


@router.get("/job-orders")
async def list_job_orders() -> list[dict]:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """SELECT j.id, j.title, j.client, j.status, j.created_at, j.spec->>'metro' AS metro,
                      j.spec->>'discipline' AS discipline,
                      r.run_id AS last_run_id, r.status AS last_run_status, r.finished_at AS last_run_at,
                      (SELECT count(*) FROM matches m WHERE m.run_id = r.run_id AND m.recommendation = 'submit')
                          AS submit_count,
                      (SELECT count(*) FROM matches m WHERE m.run_id = r.run_id AND m.status = 'proposed'
                          AND m.recommendation IN ('submit','consider')) AS pending_review
               FROM job_orders j
               LEFT JOIN LATERAL (SELECT * FROM match_runs mr WHERE mr.job_order_id = j.id
                                  ORDER BY started_at DESC LIMIT 1) r ON TRUE
               ORDER BY j.id""")
        return await cur.fetchall()


@router.get("/job-orders/{job_id}")
async def get_job_order(job_id: int) -> dict:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT id, title, client, raw_notes, spec, status, created_at FROM job_orders WHERE id=%s",
                          (job_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "job order not found")
    return row


@router.post("/job-orders/{job_id}/match")
async def start_match(job_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        run_id = await run_match(job_id, user["id"])
    except ValueError:
        raise HTTPException(404, "job order not found")
    except RunInProgress as e:
        raise HTTPException(409, str(e))
    except SpendCapReached as e:
        raise HTTPException(429, str(e))
    return {"run_id": run_id, "status": "running"}


@router.get("/job-orders/{job_id}/matches")
async def matches(job_id: int, run_id: str | None = None) -> dict:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """SELECT run_id, status, filters, relaxed, candidates, cost_usd::float AS cost_usd, error, started_at,
                      finished_at FROM match_runs WHERE job_order_id = %s AND (%s::text IS NULL OR run_id = %s)
               ORDER BY started_at DESC LIMIT 1""", (job_id, run_id, run_id))
        run = await cur.fetchone()
        if not run:
            return {"run": None, "matches": []}
        if run["status"] == "running":   # safety net: a run that's been 'running' too long is dead
            await cur.execute("SELECT now() - %s > make_interval(mins => %s) AS stale", (run["started_at"], STALE_RUN_MIN))
            if (await cur.fetchone())["stale"]:
                await conn.execute("UPDATE match_runs SET status='failed', error='timed out', finished_at=now() "
                                   "WHERE run_id=%s AND status='running'", (run["run_id"],))
                run = {**run, "status": "failed", "error": "timed out; please run matching again"}
        await cur.execute(
            """SELECT m.id, m.person_id, m.resume_file_id, m.score, m.recommendation, m.verdicts, m.flags, m.summary,
                      m.retrieval_rank, m.status, c.full_name, c.headline, c.metro, c.years_experience,
                      c.license_codes, c.quality
               FROM matches m JOIN current_candidates c ON c.person_id = m.person_id
               WHERE m.run_id = %s ORDER BY m.score DESC, m.retrieval_rank""", (run["run_id"],))
        return {"run": run, "matches": await cur.fetchall()}


class Decision(BaseModel):
    status: str = Field(pattern="^(approved|rejected|proposed)$")


@router.post("/matches/{match_id}/decision")
async def decide(match_id: int, body: Decision, user: dict = Depends(current_user)) -> dict:
    async with pool().connection() as conn:
        cur = await conn.execute(
            "UPDATE matches SET status=%s, decided_by=%s, decided_at=now() WHERE id=%s RETURNING id",
            (body.status, user["id"], match_id))
        if not await cur.fetchone():
            raise HTTPException(404, "match not found")
    return {"id": match_id, "status": body.status}


@dev_router.post("/seed")
async def seed_job_orders(user: dict = Depends(current_user)) -> dict:
    """Dev only: create job orders from the synthetic recruiter notes (idempotent by JO id)."""
    jos = json.loads((PUBLIC / "job_orders.json").read_text())
    async with pool().connection() as conn:
        cur = await conn.execute("SELECT source_ref FROM job_orders WHERE source_ref IS NOT NULL")
        existing = {r[0] for r in await cur.fetchall()}
    created, errors = 0, {}
    for jo in jos:
        if not jo.get("notes") or jo["job_order_id"] in existing:   # skip: no paid call for existing ones
            continue
        try:
            row = await _create(jo["notes"], user["id"], source_ref=jo["job_order_id"])
            created += 1 if row.get("id") else 0
        except Exception as e:  # keep going; report per job order
            errors[jo["job_order_id"]] = f"{type(e).__name__}: {str(e)[:200]}"
    return {"created": created, "skipped_existing": len(existing), "errors": errors, "total": len(jos)}
