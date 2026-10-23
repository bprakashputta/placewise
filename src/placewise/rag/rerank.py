"""Second-stage reranking with Voyage rerank-3 (a cross-encoder: reads query and passage together).

Bounded (15 s timeout, 2 retries) and logged in llm_calls like every other AI call, so the AI costs page
sees it. Cost uses VOYAGE_RERANK_USD_PER_MTOK (config; 0 while the account is on Voyage's free allowance).
"""
from __future__ import annotations

import time

import voyageai

from ..config import get_settings
from ..ingest.spend import log_call
from .retrieve import Hit

RERANK_MODEL = "rerank-3"
_client: voyageai.AsyncClient | None = None


async def rerank(query: str, hits: list[Hit], top_k: int = 30, run_ref: str = "search") -> list[Hit]:
    global _client
    if not hits:
        return []
    if _client is None:
        _client = voyageai.AsyncClient(timeout=15, max_retries=2)
    t0 = time.perf_counter()
    res = await _client.rerank(query, [h.content for h in hits], model=RERANK_MODEL, top_k=min(top_k, len(hits)))
    tokens = int(getattr(res, "total_tokens", 0) or 0)
    await log_call(run_ref, "voyage.rerank", RERANK_MODEL, 0, tokens, 0, int((time.perf_counter() - t0) * 1000),
                   tokens / 1e6 * get_settings().voyage_rerank_usd_per_mtok, "ok")
    out = []
    for r in res.results:
        h = hits[r.index]
        h.rerank = float(r.relevance_score)
        out.append(h)
    return out
