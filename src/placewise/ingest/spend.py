"""Daily LLM spend cap (protects the public demo link). Sum of today's llm_calls.cost_usd."""
from ..config import get_settings
from ..db import pool


class SpendCapReached(RuntimeError):
    pass


async def spent_today() -> float:
    async with pool().connection() as conn:
        cur = await conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE created_at >= date_trunc('day', now())")
        return float((await cur.fetchone())[0])


async def check() -> None:
    cap = get_settings().daily_llm_spend_cap_usd
    spent = await spent_today()
    if spent >= cap:
        raise SpendCapReached(f"daily LLM spend cap reached (${spent:.2f} of ${cap:.2f}); will retry later")


async def log_call(run_ref: str, step: str, model: str, prompt_version: int, inp: int, out: int, latency_ms: int,
                   cost: float, status: str, error: str | None = None, cached: int = 0) -> None:
    async with pool().connection() as conn:
        await conn.execute(
            """INSERT INTO llm_calls (run_ref, step, model, prompt_version, input_tokens, output_tokens, cached_tokens,
               latency_ms, cost_usd, status, error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run_ref, step, model, prompt_version, inp, out, cached, latency_ms, round(cost, 6), status, error))
