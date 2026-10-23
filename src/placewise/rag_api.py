"""RAG API: ask questions (cited answers) and smart candidate search. Requires a signed-in user."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from .ingest.spend import SpendCapReached
from .ingest.spend import check as spend_check
from .rag.graph import ask as run_ask
from .rag.graph import _profiles
from .rag.rerank import rerank
from .rag.retrieve import Filters, group_by_candidate, hybrid

router = APIRouter(prefix="/api", tags=["rag"])


def clean_excerpt(content: str, n: int = 260) -> str:
    """Strip the '[headline | discipline] section:' context prefix stored with each chunk."""
    import re
    text = re.sub(r"^\[[^\]]*\]\s*\w+:\s*", "", content).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if len(v.strip()) < 3:   # whitespace-only questions must never reach the paid model
            raise ValueError("question is empty")
        return v.strip()
    filters: Filters | None = None   # optional: override the filters the model would infer


@router.post("/ask")
async def ask(body: AskBody) -> dict:
    try:
        return await run_ask(body.question.strip(), body.filters.model_dump() if body.filters else None)
    except SpendCapReached as e:
        raise HTTPException(429, str(e))


@router.get("/search")
async def search(q: str = Query(min_length=2, max_length=300), discipline: str | None = None, metro: str | None = None, license: str | None = None,
                 min_years: float | None = None, limit: int = 20) -> dict:
    """Semantic + keyword candidate search with optional hard filters (no LLM call, ~0.5 s).
    Uses Voyage (embedding + rerank), so it respects the daily AI spend cap like every other AI call."""
    try:
        await spend_check()
    except SpendCapReached as e:
        raise HTTPException(429, str(e))
    f = Filters(discipline=discipline, metro=metro, license_codes=[license] if license else [], min_years=min_years)
    hits = await hybrid(q, f, k=60)
    hits = await rerank(q, hits[:60], top_k=40)
    groups = group_by_candidate(hits, "rerank")[: max(1, min(limit, 50))]
    profiles = await _profiles([g.person_id for g in groups])
    items = []
    for g in groups:
        p = profiles.get(g.person_id)
        if p:
            items.append({**{k: p[k] for k in ("person_id", "full_name", "headline", "discipline", "metro", "city",
                                                "years_experience", "license_codes", "quality")},
                          "score": round(g.score, 4), "match": clean_excerpt(g.chunks[0].content) if g.chunks else ""})
    return {"query": q, "items": items}
