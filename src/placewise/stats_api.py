"""Dashboard stats (any signed-in user) and AI cost reporting (admins)."""
from fastapi import APIRouter, Depends
from psycopg.rows import dict_row

from .auth import current_user, require_admin
from .config import get_settings
from .db import pool

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", dependencies=[Depends(current_user)])
async def stats() -> dict:
    async with pool().connection() as conn:
        one = lambda sql: conn.execute(sql)  # noqa: E731
        cands = (await (await one("SELECT count(*) FROM current_candidates")).fetchone())[0]
        attention = (await (await one("SELECT count(*) FROM resume_files WHERE status='needs_attention'")).fetchone())[0]
        processed = (await (await one("SELECT count(*) FROM resume_files WHERE status='processed'")).fetchone())[0]
        jobs = {s: n for s, n in await (await one("SELECT status, count(*) FROM ingest_jobs GROUP BY 1")).fetchall()}
        quality = {q: n for q, n in await (await one(
            "SELECT quality, count(*) FROM current_candidates GROUP BY 1")).fetchall()}
        today = (await (await one("SELECT COALESCE(sum(cost_usd),0) FROM llm_calls "
                                  "WHERE created_at >= date_trunc('day', now())")).fetchone())[0]
        total = (await (await one("SELECT COALESCE(sum(cost_usd),0) FROM llm_calls")).fetchone())[0]
        open_jobs = (await (await one("SELECT count(*) FROM job_orders WHERE status='open'")).fetchone())[0]
        to_review = (await (await one(
            """SELECT count(DISTINCT m.job_order_id) FROM matches m
               JOIN (SELECT DISTINCT ON (job_order_id) run_id FROM match_runs WHERE status='done'
                     ORDER BY job_order_id, started_at DESC) latest ON latest.run_id = m.run_id
               WHERE m.status = 'proposed' AND m.recommendation IN ('submit','consider')""")).fetchone())[0]
    return {"candidates": cands, "needs_attention": attention, "files_processed": processed, "ingest_jobs": jobs,
            "by_quality": quality, "ai_spend_today_usd": round(float(today), 4),
            "ai_spend_total_usd": round(float(total), 4), "spend_cap_usd": get_settings().daily_llm_spend_cap_usd,
            "open_job_orders": open_jobs, "shortlists_to_review": to_review}


@router.get("/admin/costs", dependencies=[Depends(require_admin)])
async def costs() -> dict:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("""SELECT to_char(date_trunc('day', created_at), 'YYYY-MM-DD') AS day, count(*) AS calls,
                                    round(sum(cost_usd), 4)::float AS cost_usd
                             FROM llm_calls GROUP BY 1 ORDER BY 1""")
        by_day = await cur.fetchall()
        await cur.execute("""SELECT step, model, count(*) AS calls, sum(input_tokens)::int AS input_tokens,
                                    sum(output_tokens)::int AS output_tokens, round(sum(cost_usd), 4)::float AS cost_usd
                             FROM llm_calls GROUP BY 1, 2 ORDER BY cost_usd DESC""")
        by_step = await cur.fetchall()
        await cur.execute("SELECT COALESCE(sum(cost_usd),0)::float AS s FROM llm_calls "
                          "WHERE created_at >= date_trunc('day', now())")
        today = (await cur.fetchone())["s"]
    return {"spend_cap_usd": get_settings().daily_llm_spend_cap_usd, "spent_today_usd": round(today, 4),
            "by_day": by_day, "by_step_model": by_step}
