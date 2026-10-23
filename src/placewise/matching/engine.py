"""Job-order extraction and candidate matching.

Matching = hard filters from must-haves (relaxed step by step if too few pass)
  → hybrid retrieval + rerank on the job's requirements → top N candidates
  → per-candidate assessment in parallel (Sonnet, anonymized profile)
  → code: license/years/location verdicts from verified fields, evidence quotes verified, score computed
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
import warnings

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from psycopg.rows import dict_row

from ..db import pool
from ..ingest.spend import check as spend_check
from ..ingest.spend import log_call
from ..promptlib import load
from ..rag.rerank import rerank
from ..rag.retrieve import Filters, _where, group_by_candidate, hybrid
from .schema import JobSpec, MatchAssessment, Requirement, RequirementVerdict

PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}
TOP_N, MIN_POOL, CONCURRENCY = 12, 5, 6
# ONE limiter for the whole process: concurrent match runs share it, so many recruiters starting
# matches at once can't exceed the Anthropic rate limit (the eval hit 429s with a per-run limiter).
_SEM: asyncio.Semaphore | None = None


def _sem() -> asyncio.Semaphore:
    global _SEM
    if _SEM is None:
        _SEM = asyncio.Semaphore(CONCURRENCY)
    return _SEM
MATCH_PROMPT_VERSION = 2
MIN_QUOTE_CHARS = 12
STALE_RUN_MIN = 10
WEIGHT = {"must": 3.0, "nice": 1.0}
VALUE = {"met": 1.0, "partial": 0.5, "unknown": 0.25, "not_met": 0.0}
_models: dict = {}
_tasks: set = set()


class RunInProgress(Exception):
    pass


async def fail_interrupted_runs() -> int:
    """At startup: runs still 'running' were interrupted (restart, crash). Mark them failed so the UI recovers."""
    async with pool().connection() as conn:
        cur = await conn.execute("UPDATE match_runs SET status='failed', error='interrupted (the server restarted '"
                                 "'during the run); please run matching again', finished_at=now() "
                                 "WHERE status='running'")
        return cur.rowcount


def _structured(model_id: str, schema):
    if (model_id, schema.__name__) not in _models:
        llm = ChatAnthropic(model=model_id, max_tokens=3000, max_retries=6, timeout=90)   # backs off on 429
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            _models[(model_id, schema.__name__)] = llm.with_structured_output(schema, include_raw=True)
    return _models[(model_id, schema.__name__)]


def _cost(model: str, raw) -> tuple[float, int, int]:
    u = getattr(raw, "usage_metadata", None) or {}
    pin, pout = PRICES.get(model, (0, 0))
    i, o = u.get("input_tokens", 0), u.get("output_tokens", 0)
    return i / 1e6 * pin + o / 1e6 * pout, i, o


# ----------------------------------------------------------------------------- job orders

async def extract_job(notes: str) -> tuple[JobSpec, float]:
    await spend_check()
    p = load("job_order_extract", 1)
    t0 = time.perf_counter()
    out = await _structured(p["model"], JobSpec).ainvoke(
        [SystemMessage(p["system"]), HumanMessage(p["user"].format(notes=notes[:6000]))],
        config={"run_name": "extract_job_order", "tags": ["job_order"]})
    cost, i, o = _cost(p["model"], out.get("raw"))
    await log_call("job_order", "job_order.extract", p["model"], 1, i, o, int((time.perf_counter() - t0) * 1000),
                   cost, "ok" if out.get("parsed") else "invalid_output")
    if out.get("parsed") is None:
        raise RuntimeError(f"couldn't structure the job order: {out.get('parsing_error')}")
    return out["parsed"], cost


# ----------------------------------------------------------------------------- filters

def hard_filters(spec: JobSpec) -> list[tuple[str, Filters]]:
    """Strict filters first, then progressively relaxed versions (label, filters)."""
    f = Filters(discipline=spec.discipline if spec.discipline != "other" else None)
    for r in spec.requirements:
        if r.priority != "must":
            continue
        if r.kind == "license" and r.key and r.state and not re.search(r"\bor\b", r.text, re.I):
            f.license_codes.append(f"{r.key.upper()}:{r.state.upper()}")
        elif r.kind == "location" and spec.metro:
            f.metro = spec.metro
        elif r.kind == "years":
            yrs = _years(r) or spec.min_years
            if yrs:
                f.min_years = max(0.0, yrs - 1)   # one year short can still be 'partial'
    if spec.metro and not f.metro:
        f.metro = spec.metro
    steps = [("strict", f)]
    if f.min_years is not None:
        steps.append(("years", f.model_copy(update={"min_years": None})))
    if f.metro:
        steps.append(("metro", steps[-1][1].model_copy(update={"metro": None})))
    if f.license_codes:
        steps.append(("license", steps[-1][1].model_copy(update={"license_codes": []})))
    return steps


def _years(r: Requirement) -> float | None:
    m = re.search(r"\d+(\.\d+)?", r.value or r.text or "")
    return float(m.group(0)) if m else None


async def _count(f: Filters) -> int:
    where, args = _where(f)
    async with pool().connection() as conn:
        cur = await conn.execute(f"""SELECT count(*) FROM current_candidates p
                                     JOIN resume_files rf ON rf.id = p.resume_file_id WHERE {where}""", args)
        return (await cur.fetchone())[0]


# ----------------------------------------------------------------------------- code verdicts

def code_verdict(r: Requirement, spec: JobSpec, prof: dict) -> RequirementVerdict | None:
    """Verdicts for facts we have VERIFIED fields for. Returns None for soft requirements (LLM judges)."""
    codes = prof.get("license_codes") or []
    if r.kind == "license" and r.key:
        key = r.key.upper()
        alts = [key] + (["PE"] if key == "EIT" else [])        # "EIT or PE": a PE satisfies it
        if r.state:
            if any(f"{k}:{r.state.upper()}" in codes for k in alts):
                return RequirementVerdict(requirement=r.text, verdict="met", evidence=None,
                                          note=f"Active {key} license in {r.state.upper()} (stated on resume)")
            other = [c for c in codes if c.split(":")[0] in alts]
            if other:
                return RequirementVerdict(requirement=r.text, verdict="partial", evidence=None,
                                          note=f"License is in another state: {', '.join(other)}")
            return RequirementVerdict(requirement=r.text, verdict="not_met", evidence=None,
                                      note=f"No active {key} license on record")
        if any(c.split(":")[0] in alts for c in codes):
            return RequirementVerdict(requirement=r.text, verdict="met", evidence=None, note=f"{key} listed on resume")
        return RequirementVerdict(requirement=r.text, verdict="not_met", evidence=None,
                                  note=f"No active {key} on record")
    if r.kind == "years":
        need, have = _years(r) or spec.min_years, prof.get("years_experience")
        if need is None or have is None:
            return None
        v = "met" if have >= need else ("partial" if have >= need - 1 else "not_met")
        return RequirementVerdict(requirement=r.text, verdict=v, evidence=None,
                                  note=f"{have:g} years (computed from resume dates)")
    if r.kind == "location" and spec.metro:
        same_place = prof.get("metro") == spec.metro and (
            spec.metro != "Other" or (spec.city or "").lower() == (prof.get("city") or "").lower())
        if same_place:
            return RequirementVerdict(requirement=r.text, verdict="met", evidence=None, note=f"Based in {spec.metro}")
        if prof.get("open_to_relocation"):
            return RequirementVerdict(requirement=r.text, verdict="partial", evidence=None,
                                      note=f"Based in {prof.get('metro')}, open to relocation")
        return RequirementVerdict(requirement=r.text, verdict="not_met", evidence=None,
                                  note=f"Based in {prof.get('metro')}, relocation not stated")
    if r.kind == "discipline":
        ok = prof.get("discipline") == spec.discipline
        label = (prof.get("discipline") or "unknown").replace("_", " ").capitalize()
        return RequirementVerdict(requirement=r.text, verdict="met" if ok else "not_met", evidence=None,
                                  note=None if ok else f"Discipline on resume: {label}")
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("–", "-").replace("—", "-")).strip().lower()


def score(spec: JobSpec, verdicts: list[RequirementVerdict]) -> tuple[float, str]:
    by_text = {v.requirement: v for v in verdicts}
    num = den = 0.0
    gate_fail = gate_partial = False
    for r in spec.requirements:
        v = by_text.get(r.text)
        w = WEIGHT[r.priority]
        den += w
        num += w * VALUE[v.verdict if v else "unknown"]
        if r.priority == "must" and r.kind in ("license", "discipline") and v and v.verdict == "not_met":
            gate_fail = True
        # A must-have license held only in another state (or a relocation instead of local) is never an
        # automatic "submit": the recruiter must confirm it first.
        if r.priority == "must" and r.kind in ("license", "location") and v and v.verdict == "partial":
            gate_partial = True
    s = round(100 * num / den, 1) if den else 0.0
    if gate_fail:
        s = min(s, 40.0)
    if gate_fail:
        rec = "pass"
    elif s >= 80 and not gate_partial:
        rec = "submit"
    elif s >= 55:
        rec = "consider"
    else:
        rec = "pass"
    return s, rec


async def assess(spec: JobSpec, prof: dict, sem: asyncio.Semaphore, run_id: str) -> dict:
    code = {r.text: cv for r in spec.requirements if (cv := code_verdict(r, spec, prof))}
    soft = [r for r in spec.requirements if r.text not in code]
    facts = (f"licenses: {', '.join(prof.get('license_codes') or []) or 'none'}; "
             f"years: {prof.get('years_experience')}; metro: {prof.get('metro')}; "
             f"open to relocation: {bool(prof.get('open_to_relocation'))}")
    verdicts, flags, summary, cost = list(code.values()), [], "", 0.0
    if soft:
        async with sem:
            await spend_check()
            p = load("match_score", MATCH_PROMPT_VERSION)
            reqs = "\n".join(f"- [{r.priority}] {r.text}" for r in soft)
            t0 = time.perf_counter()
            out = await _structured(p["model"], MatchAssessment).ainvoke(
                [SystemMessage(p["system"]), HumanMessage(p["user"].format(
                    title=spec.title, requirements=reqs, job_metro=spec.metro or "not specified", facts=facts,
                    profile=(prof.get("blind_text") or "")[:12000]))],
                config={"run_name": "score_candidate", "tags": ["match"], "metadata": {"run_id": run_id}})
            cost, i, o = _cost(p["model"], out.get("raw"))
            await log_call(run_id, "match.score", p["model"], MATCH_PROMPT_VERSION, i, o, int((time.perf_counter() - t0) * 1000), cost,
                           "ok" if out.get("parsed") else "invalid_output")
        a: MatchAssessment | None = out.get("parsed")
        if a:
            flags, summary = list(a.flags), a.summary
            text = _norm(prof.get("blind_text") or "")
            soft_texts = {r.text for r in soft}
            for v in a.verdicts:
                if v.requirement not in soft_texts:
                    continue
                ev = _norm(v.evidence or "")
                if v.verdict in ("met", "partial"):
                    # A positive verdict needs a real quote: present, long enough not to match by accident
                    # (e.g. "PE"), and actually found in the profile text.
                    if not ev:
                        v.note, v.verdict = "no evidence quote given", "unknown"
                        flags.append("unsupported verdict downgraded")
                    elif len(ev) < MIN_QUOTE_CHARS or ev not in text:
                        v.note = f"evidence not found in profile: {(v.evidence or '')[:80]!r}"
                        v.evidence, v.verdict = None, "unknown"
                        flags.append("unverified evidence removed")
                verdicts.append(v)
    for cv in code.values():   # surface code-detected license risks as flags too
        if cv.verdict == "partial" and "another state" in (cv.note or ""):
            flags.append(cv.note)
    s, rec = score(spec, verdicts)
    return {"person_id": prof["person_id"], "resume_file_id": prof["resume_file_id"], "score": s,
            "recommendation": rec, "verdicts": [v.model_dump() for v in verdicts], "flags": sorted(set(flags)),
            "summary": summary, "cost": cost}


# ----------------------------------------------------------------------------- run

async def run_match(job_order_id: int, user_id: int | None = None) -> str:
    async with pool().connection() as conn:
        cur = await conn.execute("SELECT spec FROM job_orders WHERE id = %s", (job_order_id,))
        row = await cur.fetchone()
    if not row:
        raise ValueError("job order not found")
    spec = JobSpec.model_validate(row[0])
    await spend_check()   # refuse up front (clean 429) instead of failing every assessment later
    async with pool().connection() as conn:
        cur = await conn.execute(
            "SELECT run_id FROM match_runs WHERE job_order_id=%s AND status='running' "
            "AND started_at > now() - make_interval(mins => %s)", (job_order_id, STALE_RUN_MIN))
        if await cur.fetchone():
            raise RunInProgress("a match is already running for this job order")
    run_id = f"m-{uuid.uuid4().hex[:10]}"
    steps = hard_filters(spec)
    relaxed: list[str] = []
    chosen = steps[0][1]
    for i, (label, f) in enumerate(steps):   # loosen filters one at a time until enough candidates pass
        chosen = f
        if i > 0:
            relaxed.append(label)
        if await _count(f) >= MIN_POOL:
            break
    async with pool().connection() as conn:
        await conn.execute("INSERT INTO match_runs (run_id, job_order_id, filters, relaxed, created_by) "
                           "VALUES (%s,%s,%s,%s,%s)", (run_id, job_order_id, chosen.model_dump_json(), relaxed, user_id))
    task = asyncio.create_task(_finish(run_id, job_order_id, spec, chosen))
    _tasks.add(task)                      # keep a reference so the task isn't garbage-collected
    task.add_done_callback(_tasks.discard)
    return run_id


async def _finish(run_id: str, job_order_id: int, spec: JobSpec, f: Filters) -> None:
    try:
        query = spec.title + ". " + "; ".join(r.text for r in spec.requirements)
        hits = await hybrid(query, f, k=80)
        hits = await rerank(query, hits[:60], top_k=50)
        groups = group_by_candidate(hits, "rerank")[:TOP_N]
        ids = [g.person_id for g in groups]
        async with pool().connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute("""SELECT c.person_id, c.resume_file_id, c.discipline, c.metro, c.years_experience,
                                        c.license_codes, c.open_to_relocation, pr.blind_text
                                 FROM current_candidates c JOIN profiles pr ON pr.resume_file_id = c.resume_file_id
                                 WHERE c.person_id = ANY(%s)""", (ids,))
            profs = {r["person_id"]: r for r in await cur.fetchall()}
        results = await asyncio.gather(*(assess(spec, profs[pid], _sem(), run_id) for pid in ids if pid in profs),
                                       return_exceptions=True)
        ok = [r for r in results if isinstance(r, dict)]
        rank = {pid: i + 1 for i, pid in enumerate(ids)}
        async with pool().connection() as conn:
            async with conn.transaction():
                for r in ok:
                    await conn.execute(
                        """INSERT INTO matches (job_order_id, run_id, person_id, resume_file_id, score, recommendation,
                               verdicts, flags, summary, retrieval_rank) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (job_order_id, run_id, r["person_id"], r["resume_file_id"], r["score"], r["recommendation"],
                         json.dumps(r["verdicts"]), r["flags"], r["summary"], rank[r["person_id"]]))
                errs = sorted({repr(r)[:200] for r in results if not isinstance(r, dict)})   # dedupe repeats
                status = "done" if ok or not results else "failed"   # every assessment failed → failed run
                await conn.execute(
                    "UPDATE match_runs SET status=%s, candidates=%s, cost_usd=%s, error=%s, finished_at=now() "
                    "WHERE run_id=%s", (status, len(ok), round(sum(r["cost"] for r in ok), 5),
                                        "; ".join(errs) or None, run_id))
    except Exception as e:
        async with pool().connection() as conn:
            await conn.execute("UPDATE match_runs SET status='failed', error=%s, finished_at=now() WHERE run_id=%s",
                               (f"{type(e).__name__}: {e}"[:1000], run_id))
