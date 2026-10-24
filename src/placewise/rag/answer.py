"""Question understanding (Haiku) and cited answers (Sonnet), both with structured output.

Citations are verified by code: a citation survives only if its chunk was actually retrieved and its
quote appears in that chunk's text. Unverifiable citations are dropped and reported.
"""
from __future__ import annotations

import re
import time
import warnings

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..llm_cache import response_cache
from ..llm_cost import cached_system, usage_cost
from ..promptlib import load
from .retrieve import Filters, Hit


class QueryPlan(BaseModel):
    filters: Filters = Field(default_factory=Filters)
    search_query: str


class Citation(BaseModel):
    chunk_id: int
    quote: str = Field(description="Short text copied exactly from that section")


class RagAnswer(BaseModel):
    answer: str = Field(description="Markdown: one intro sentence, then bullets per candidate")
    citations: list[Citation] = Field(default_factory=list)


_models: dict[tuple, object] = {}


def _structured(model_id: str, schema):
    key = (model_id, schema.__name__)
    if key not in _models:
        # cache=: the same question over the same retrieved sections replays for $0
        llm = ChatAnthropic(model=model_id, max_tokens=3000, max_retries=3, timeout=60,
                            cache=response_cache(schema))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _models[key] = llm.with_structured_output(schema, include_raw=True)
    return _models[key]


def _usage(model: str, usage: dict) -> dict:
    """Usage fields for logging: tokens, cache reads and the cost (cache-aware)."""
    c = usage_cost(model, usage)
    return {"cost_usd": c["usd"], "input_tokens": c["input_tokens"], "output_tokens": c["output_tokens"],
            "cache_read": c["cache_read"], "response_cache": c["response_cache"]}


async def understand(question: str) -> tuple[QueryPlan, dict]:
    p = load("rag_understand", 1)
    t0 = time.perf_counter()
    try:
        out = await _structured(p["model"], QueryPlan).ainvoke(
            [SystemMessage(p["system"]), HumanMessage(p["user"].format(question=question[:2000]))],
            config={"run_name": "understand_question", "tags": ["rag"]})
        plan = out.get("parsed") or QueryPlan(search_query=question)
        usage = getattr(out.get("raw"), "usage_metadata", None) or {}
    except Exception:  # degrade gracefully: no filters, search the raw question
        plan, usage = QueryPlan(search_query=question), {}
    plan.filters.license_codes = [c.upper().replace(" ", "") for c in plan.filters.license_codes]
    return plan, {"model": p["model"], "latency_ms": int((time.perf_counter() - t0) * 1000), **_usage(p["model"], usage)}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("–", "-").replace("—", "-")).strip().lower()


ANSWER_PROMPT_VERSION = 2


def _facts(p: dict) -> str:
    lic = ", ".join(c.replace(":", " in ") for c in p.get("license_codes") or []) or "none verified"
    reloc = "open to relocation" if p.get("open_to_relocation") else "not stated as open to relocation"
    return (f"licenses: {lic}; years of experience: {p.get('years_experience')}; "
            f"location: {p.get('city')}, {p.get('metro')} ({reloc})")


async def answer(question: str, hits: list[Hit], names: dict[int, str], profiles: dict[int, dict] | None = None,
                 filters_text: str = "none") -> tuple[RagAnswer, dict, list[str]]:
    p = load("rag_answer", ANSWER_PROMPT_VERSION)
    profiles = profiles or {}
    blocks, seen = [], []
    for h in hits:
        if h.person_id not in seen:
            seen.append(h.person_id)
    for pid in seen:
        prof = profiles.get(pid, {})
        lines = [f"### {names.get(pid, 'Candidate')}", f"VERIFIED FACTS: {_facts(prof)}" if prof else ""]
        lines += [f"[id {h.chunk_id}] {h.section}: {h.content}" for h in hits if h.person_id == pid]
        blocks.append("\n".join(x for x in lines if x))
    sections = "\n\n".join(blocks)
    t0 = time.perf_counter()
    out = await _structured(p["model"], RagAnswer).ainvoke(
        # Tool schema + instructions are cached: follow-up questions within 5 minutes reuse them.
        [cached_system(p["system"]), HumanMessage(p["user"].format(question=question[:2000], filters=filters_text,
                                                                   sections=sections))],
        config={"run_name": "answer_with_citations", "tags": ["rag"]})
    ans: RagAnswer = out.get("parsed") or RagAnswer(answer="I couldn't produce an answer this time. Please retry.")
    usage = getattr(out.get("raw"), "usage_metadata", None) or {}
    by_id = {h.chunk_id: h for h in hits}
    kept, dropped = [], []
    for c in ans.citations:
        h = by_id.get(c.chunk_id)
        q = _norm(c.quote)
        if h is not None and len(q) >= 12 and q in _norm(h.content):   # short quotes could match by accident
            kept.append(c)
        else:
            dropped.append(f"citation to section {c.chunk_id} not found in retrieved text: {c.quote[:80]!r}")
    ans.citations = kept
    return ans, {"model": p["model"], "latency_ms": int((time.perf_counter() - t0) * 1000),
                 **_usage(p["model"], usage)}, dropped
