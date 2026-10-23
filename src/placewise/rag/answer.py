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

from ..promptlib import load
from .retrieve import Filters, Hit

PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}


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
        llm = ChatAnthropic(model=model_id, max_tokens=3000, max_retries=3, timeout=60)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _models[key] = llm.with_structured_output(schema, include_raw=True)
    return _models[key]


def _cost(model: str, usage: dict) -> float:
    pin, pout = PRICES.get(model, (0, 0))
    return usage.get("input_tokens", 0) / 1e6 * pin + usage.get("output_tokens", 0) / 1e6 * pout


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
    return plan, {"model": p["model"], "cost_usd": _cost(p["model"], usage),
                  "latency_ms": int((time.perf_counter() - t0) * 1000), **usage}


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
        [SystemMessage(p["system"]), HumanMessage(p["user"].format(question=question[:2000], filters=filters_text,
                                                                   sections=sections))],
        config={"run_name": "answer_with_citations", "tags": ["rag"]})
    ans: RagAnswer = out.get("parsed") or RagAnswer(answer="I couldn't produce an answer this time. Please retry.")
    usage = getattr(out.get("raw"), "usage_metadata", None) or {}
    by_id = {h.chunk_id: h for h in hits}
    kept, dropped = [], []
    for c in ans.citations:
        h = by_id.get(c.chunk_id)
        if h is not None and _norm(c.quote) and _norm(c.quote) in _norm(h.content):
            kept.append(c)
        else:
            dropped.append(f"citation to section {c.chunk_id} not found in retrieved text: {c.quote[:80]!r}")
    ans.citations = kept
    return ans, {"model": p["model"], "cost_usd": _cost(p["model"], usage),
                 "latency_ms": int((time.perf_counter() - t0) * 1000), **usage}, dropped
