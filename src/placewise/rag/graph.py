"""The RAG graph (LangGraph), one LangSmith trace per question:

    understand (Haiku: filters + search query) → retrieve (hybrid, current resumes only)
      → rerank (Voyage rerank-3) → answer (Sonnet, cited) → citations verified by code
"""
from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row

from ..db import pool
from ..ingest.spend import check as spend_check
from ..ingest.spend import log_call
from .answer import ANSWER_PROMPT_VERSION, QueryPlan, answer, understand
from .rerank import rerank
from .retrieve import Filters, Hit, group_by_candidate, hybrid

MAX_ANSWER_CANDIDATES, CHUNKS_PER_CANDIDATE = 8, 2


class AskState(TypedDict, total=False):
    question: str
    filters_override: dict | None
    plan_override: dict | None        # a ready plan (e.g. from a job order's requirements): skip understand
    person_ids: list[int] | None      # follow-ups: restrict the search to these candidates
    plan: dict
    hits: list
    candidates: list
    names: dict
    answer: dict
    dropped: list
    usage: dict
    timings: dict


async def _profiles(person_ids: list[int]) -> dict[int, dict]:
    if not person_ids:
        return {}
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """SELECT person_id, resume_file_id, full_name, headline, discipline, metro, city, years_experience,
                      license_codes, quality, open_to_relocation
               FROM current_candidates WHERE person_id = ANY(%s)""", (person_ids,))
        return {r["person_id"]: r for r in await cur.fetchall()}


async def _credential_chunks(person_ids: list[int]) -> list[Hit]:
    if not person_ids:
        return []
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("""SELECT id, person_id, resume_file_id, section, content FROM current_chunks
                             WHERE section = 'credentials' AND person_id = ANY(%s)""", (person_ids,))
        return [Hit(r["id"], r["person_id"], r["resume_file_id"], r["section"], r["content"])
                for r in await cur.fetchall()]


async def n_understand(s: AskState) -> AskState:
    await spend_check()
    t0 = time.perf_counter()
    if s.get("plan_override"):
        return {"plan": QueryPlan.model_validate(s["plan_override"]).model_dump(), "usage": {},
                "timings": {"understand_ms": 0}}
    plan, usage = await understand(s["question"])
    if s.get("filters_override"):
        plan.filters = Filters(**s["filters_override"])
    await log_call("ask", "rag.understand", usage["model"], 1, usage.get("input_tokens", 0),
                   usage.get("output_tokens", 0), usage["latency_ms"], usage["cost_usd"], "ok")
    return {"plan": plan.model_dump(), "usage": {"understand": usage},
            "timings": {"understand_ms": int((time.perf_counter() - t0) * 1000)}}


async def n_retrieve(s: AskState) -> AskState:
    t0 = time.perf_counter()
    plan = QueryPlan.model_validate(s["plan"])
    hits = await hybrid(plan.search_query or s["question"], plan.filters, k=60, person_ids=s.get("person_ids"), run_ref="ask")
    return {"hits": hits, "timings": {**s["timings"], "retrieve_ms": int((time.perf_counter() - t0) * 1000)}}


async def n_rerank(s: AskState) -> AskState:
    t0 = time.perf_counter()
    q = QueryPlan.model_validate(s["plan"]).search_query or s["question"]
    hits = await rerank(q, s["hits"][:60], top_k=40, run_ref="ask") if s["hits"] else []
    groups = group_by_candidate(hits, "rerank", per_person=CHUNKS_PER_CANDIDATE)
    names = {pid: p["full_name"] for pid, p in (await _profiles([g.person_id for g in groups[:20]])).items()}
    return {"hits": hits, "candidates": groups[:20], "names": names,
            "timings": {**s["timings"], "rerank_ms": int((time.perf_counter() - t0) * 1000)}}


async def n_answer(s: AskState) -> AskState:
    t0 = time.perf_counter()
    top = [c for g in s["candidates"][:MAX_ANSWER_CANDIDATES] for c in g.chunks]
    if not top:
        return {"answer": {"answer": "No candidates match these requirements. Try loosening a filter "
                                     "(for example a license state or the metro).", "citations": []},
                "dropped": [], "timings": {**s["timings"], "answer_ms": 0}}
    await spend_check()
    # Always include each candidate's credentials section (license evidence), plus verified facts
    person_ids = [g.person_id for g in s["candidates"][:MAX_ANSWER_CANDIDATES]]
    have = {h.chunk_id for h in top}
    top += [h for h in await _credential_chunks(person_ids) if h.chunk_id not in have]
    profiles = await _profiles(person_ids)
    f = QueryPlan.model_validate(s["plan"]).filters
    parts = [f"discipline {f.discipline}" if f.discipline else "", f"metro {f.metro} (or open to relocation)"
             if f.metro else "", ", ".join(f"license {c}" for c in f.license_codes),
             f"at least {f.min_years:g} years" if f.min_years is not None else ""]
    ans, usage, dropped = await answer(s["question"], top, s["names"], profiles,
                                       "; ".join(x for x in parts if x) or "none")
    await log_call("ask", "rag.answer", usage["model"], ANSWER_PROMPT_VERSION, usage.get("input_tokens", 0),
                   usage.get("output_tokens", 0), usage["latency_ms"], usage["cost_usd"],
                   "invalid_output" if ans.answer.startswith("I couldn't produce") else "ok")
    return {"answer": ans.model_dump(), "dropped": dropped, "usage": {**s["usage"], "answer": usage},
            "timings": {**s["timings"], "answer_ms": int((time.perf_counter() - t0) * 1000)}}


def build():
    g = StateGraph(AskState)
    for name, fn in (("understand", n_understand), ("retrieve", n_retrieve), ("rerank", n_rerank),
                     ("answer", n_answer)):
        g.add_node(name, fn)
    g.add_edge(START, "understand")
    g.add_edge("understand", "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "answer")
    g.add_edge("answer", END)
    return g.compile()


GRAPH = build()


async def ask(question: str, filters_override: dict | None = None, plan_override: dict | None = None,
              person_ids: list[int] | None = None, run_name: str = "ask") -> dict[str, Any]:
    t0 = time.perf_counter()
    s = await GRAPH.ainvoke({"question": question, "filters_override": filters_override,
                             "plan_override": plan_override, "person_ids": person_ids},
                            config={"run_name": run_name, "tags": ["rag", "ask"],
                                    "metadata": {"question": question[:200]}})
    profiles = await _profiles([g.person_id for g in s["candidates"]])
    by_chunk = {h.chunk_id: h for h in s["hits"]}
    by_chunk.update({h.chunk_id: h for h in await _credential_chunks([g.person_id for g in s["candidates"]
                                                                       [:MAX_ANSWER_CANDIDATES]])})
    citations = []
    for c in s["answer"]["citations"]:
        h = by_chunk[c["chunk_id"]]
        citations.append({"chunk_id": h.chunk_id, "person_id": h.person_id, "resume_file_id": h.resume_file_id,
                          "candidate_name": s["names"].get(h.person_id), "section": h.section, "quote": c["quote"]})
    candidates = []
    for g in s["candidates"]:
        p = profiles.get(g.person_id)
        if not p:
            continue
        candidates.append({**{k: p[k] for k in ("person_id", "full_name", "headline", "discipline", "metro", "city",
                                                 "years_experience", "license_codes", "quality")},
                           "score": round(g.score, 4),
                           "top_sections": [{"chunk_id": c.chunk_id, "section": c.section, "content": c.content[:400]}
                                            for c in g.chunks]})
    usage = s.get("usage", {})
    return {"question": question, "answer": s["answer"]["answer"], "citations": citations, "candidates": candidates,
            "plan": s["plan"], "dropped_citations": s.get("dropped", []),
            "timings_ms": {**s["timings"], "total_ms": int((time.perf_counter() - t0) * 1000)},
            "cost_usd": round(sum(u.get("cost_usd", 0) for u in usage.values()), 5)}
