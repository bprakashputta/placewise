"""Second-stage reranking with Voyage rerank-3 (a cross-encoder: reads query and passage together)."""
from __future__ import annotations

import voyageai

from .retrieve import Hit

RERANK_MODEL = "rerank-3"
_client: voyageai.AsyncClient | None = None


async def rerank(query: str, hits: list[Hit], top_k: int = 30) -> list[Hit]:
    global _client
    if not hits:
        return []
    if _client is None:
        _client = voyageai.AsyncClient()
    res = await _client.rerank(query, [h.content for h in hits], model=RERANK_MODEL, top_k=min(top_k, len(hits)))
    out = []
    for r in res.results:
        h = hits[r.index]
        h.rerank = float(r.relevance_score)
        out.append(h)
    return out
