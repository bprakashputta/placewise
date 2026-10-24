"""Conversational Ask (ADR 018): route each chat message before any search.

    message → route (keyword shortcut, else Claude Haiku) →
        greeting / off_topic → a short reply from the router (Haiku), grounded in today's activity
        keyword greetings / help / gibberish → a reply written by code (free, instant)
        search    → RAG graph on the standalone question
        follow_up → RAG graph restricted to the candidates shown last (if the router says so)
        job_order → RAG graph with a plan built from the job order's structured requirements

Keyword greetings ("hi", "thanks") get code-built replies from live data (shortlists to review, job
orders with no run yet, new resumes today): free and instant. Small talk the model routes ("how are
you doing?") gets Haiku's short reply, which may only use the facts in TODAY'S ACTIVITY passed to it
(prompt ask_route v2). Neither path runs a search.
"""
from __future__ import annotations

import random
import re
import time
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ..db import pool
from ..ingest.spend import check as spend_check
from ..ingest.spend import log_call
from ..llm_cost import usage_cost
from ..matching.engine import hard_filters
from ..matching.schema import JobSpec
from ..promptlib import load
from .answer import _structured
from .graph import ask as run_rag

ROUTE_PROMPT_VERSION = 2
LOCAL_TZ = ZoneInfo("America/Chicago")   # the firm is in DFW; "today" and "good morning" follow local time
HISTORY_TURNS = 6
SEARCH_KINDS = ("search", "follow_up", "job_order")

Intent = Literal["greeting", "help", "search", "follow_up", "job_order", "off_topic", "unclear"]


class Route(BaseModel):
    intent: Intent
    standalone_question: str = Field("", description="Complete standalone question for search kinds, else ''")
    scope: Literal["previous_candidates", "all"] = "all"
    job_order_id: int | None = None
    reply: str = Field("", description="Only for greeting/off_topic: a short natural reply, else ''")


# ---------- routing ----------

_HELLO = r"(hi+|hey+|hello+|howdy|yo|hiya|good (morning|afternoon|evening)|morning|greetings|what'?s up|sup)"
_THANKS = r"(thanks?( you)?( so much)?|thank you|thx|ty|cheers|appreciate it|great|awesome|perfect|cool|ok(ay)?)"
_BYE = r"(bye|goodbye|see (you|ya)|later|good ?night|that'?s all)"
_TAIL = r"[\s!.,?:)]*(there|team|placewise|assistant|claude|again)?[\s!.,?:)]*"


def quick_route(message: str) -> tuple[Intent, str] | None:
    """Free shortcut for obvious one-liners. Returns (intent, flavor) or None to ask the model."""
    t = message.strip().lower()
    if len(t) > 40:
        return None
    if re.fullmatch(_HELLO + _TAIL, t):
        return "greeting", "hello"
    if re.fullmatch(_THANKS + _TAIL, t):
        return "greeting", "thanks"
    if re.fullmatch(_BYE + _TAIL, t):
        return "greeting", "bye"
    if re.fullmatch(r"(help|\?|what can you do\??|how does this work\??|what do you do\??)", t):
        return "help", ""
    if re.fullmatch(r"[^a-z0-9]*|(.)\1{3,}|[asdfghjkl;]{4,}|[qwertyuiop]{5,}", t):   # "sssss", "asdf", "???"
        return "unclear", ""
    return None


def _history_text(history: list[dict]) -> str:
    lines = []
    for m in history[-HISTORY_TURNS * 2:]:
        if m["role"] == "user":
            lines.append(f"Recruiter: {m['content'][:500]}")
        elif m["kind"] in SEARCH_KINDS:
            r = m.get("response") or {}
            cited = []
            for c in r.get("citations", []):
                if c.get("candidate_name") and c["candidate_name"] not in cited:
                    cited.append(c["candidate_name"])
            names = ", ".join(cited[:8]) or ", ".join(c["full_name"] for c in r.get("candidates", [])[:8])
            lines.append(f"Assistant: answered \"{r.get('standalone_question') or ''}\". "
                         f"Candidates discussed: {names or 'none'}.")
        else:
            lines.append(f"Assistant: {m['content'][:200]}")
    return "\n".join(lines) or "(none)"


def _job_order_context(jo: dict | None) -> str:
    if not jo:
        return "This conversation is not about a specific job order."
    spec = jo["spec"]
    musts = [r["text"] for r in spec.get("requirements", []) if r.get("priority") == "must"]
    return (f"This conversation is about job order JO-{jo['id']:02d}: {spec.get('title')} "
            f"({spec.get('metro') or 'location not set'}). Must-haves: {'; '.join(musts) or 'none listed'}.")


def today_text(ctx: dict | None) -> str:
    if not ctx:
        return "(not available)"
    facts = [f"{ctx['new_today']} new resumes processed today", f"{ctx['to_review']} job orders with a shortlist "
             f"waiting for review", f"{ctx['no_run']} open job orders with no candidates matched yet",
             f"{ctx['attention']} resumes that couldn't be read", f"{ctx.get('candidates', 0)} candidates in the pool"]
    return "; ".join(facts)


async def route(message: str, history: list[dict], jo: dict | None) -> tuple[Route, dict]:
    quick = quick_route(message)
    if quick:
        return Route(intent=quick[0]), {"flavor": quick[1], "cost_usd": 0.0}
    await spend_check()
    p = load("ask_route", ROUTE_PROMPT_VERSION)
    t0 = time.perf_counter()
    try:
        ctx = await _today_context()
    except Exception:
        ctx = None
    try:
        out = await _structured(p["model"], Route).ainvoke(
            [SystemMessage(p["system"]), HumanMessage(p["user"].format(
                history=_history_text(history), job_order_context=_job_order_context(jo), today=today_text(ctx),
                message=message[:2000]))],
            config={"run_name": "route_message", "tags": ["ask", "route"]})
        r: Route | None = out.get("parsed")
        usage = getattr(out.get("raw"), "usage_metadata", None) or {}
        status = "ok" if r else "invalid_output"
    except Exception:
        r, usage, status = None, {}, "error"
    if r is None:   # fail open to a normal search: never lose a real question
        r = Route(intent="search", standalone_question=message)
    if r.intent in SEARCH_KINDS and not r.standalone_question.strip():
        r.standalone_question = message
    c = usage_cost(p["model"], usage)
    cost = c["usd"]
    await log_call("ask", "ask.route", p["model"], ROUTE_PROMPT_VERSION, c["input_tokens"], c["output_tokens"],
                   int((time.perf_counter() - t0) * 1000), cost, "cache_hit" if c["response_cache"] else status,
                   cached=c["cache_read"])
    return r, {"flavor": "hello", "cost_usd": cost}


# ---------- replies written by code ----------

def _part_of_day(now: datetime) -> str:
    return "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"


async def _today_context() -> dict:
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """SELECT
                 (SELECT count(DISTINCT m.job_order_id) FROM matches m
                    JOIN (SELECT DISTINCT ON (job_order_id) run_id FROM match_runs WHERE status='done'
                          ORDER BY job_order_id, started_at DESC) latest ON latest.run_id = m.run_id
                    WHERE m.status='proposed' AND m.recommendation IN ('submit','consider')) AS to_review,
                 (SELECT count(*) FROM job_orders j WHERE j.status='open'
                    AND NOT EXISTS (SELECT 1 FROM match_runs r WHERE r.job_order_id=j.id)) AS no_run,
                 (SELECT min(id) FROM job_orders j WHERE j.status='open'
                    AND NOT EXISTS (SELECT 1 FROM match_runs r WHERE r.job_order_id=j.id)) AS no_run_id,
                 (SELECT count(*) FROM resume_files WHERE status='processed'
                    AND processed_at >= (date_trunc('day', now() AT TIME ZONE 'America/Chicago')
                                         AT TIME ZONE 'America/Chicago')) AS new_today,
                 (SELECT count(*) FROM resume_files WHERE status='needs_attention') AS attention,
                 (SELECT count(*) FROM current_candidates) AS candidates""")
        return await cur.fetchone()


async def _first_chat_today(user_id: int) -> bool:
    async with pool().connection() as conn:
        cur = await conn.execute(
            """SELECT 1 FROM conversation_messages m JOIN conversations c ON c.id = m.conversation_id
               WHERE c.user_id = %s AND m.role = 'user'
                 AND m.created_at >= (date_trunc('day', now() AT TIME ZONE 'America/Chicago')
                                      AT TIME ZONE 'America/Chicago') LIMIT 1""", (user_id,))
        return await cur.fetchone() is None


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def greeting_reply(flavor: str, first_name: str, first_today: bool, ctx: dict | None, now: datetime,
                   jo: dict | None) -> tuple[str, list[str]]:
    if flavor == "thanks":
        return "You're welcome! Anything else you'd like to look into?", []
    if flavor == "bye":
        return "Talk soon! Your chats are saved here whenever you come back.", []
    role_hint = (f" We're working on **{jo['spec'].get('title')}** (JO-{jo['id']:02d})." if jo else "")
    if not first_today or not ctx:
        text = random.choice([f"Hi {first_name}!{role_hint} What would you like to find?",
                              f"Hey {first_name}!{role_hint} Who are we looking for?",
                              f"Hi again, {first_name}!{role_hint} What can I dig up for you?",
                              f"Hello {first_name}!{role_hint} Tell me the role, license or skills you need."])
        sugg = ([f"Who are the top candidates for this role?"] if jo else
                ["Texas PEs in DFW with drainage experience", "What can you do?"])
        return text, sugg
    lines = []
    if ctx["to_review"]:
        lines.append(f"- {_plural(ctx['to_review'], 'job order has', 'job orders have')} a shortlist waiting for "
                     "your review (see **Job Orders**)")
    if ctx["no_run"]:
        lines.append(f"- {_plural(ctx['no_run'], 'open job order has', 'open job orders have')} no candidates "
                     "matched yet")
    if ctx["new_today"]:
        lines.append(f"- {_plural(ctx['new_today'], 'new resume was', 'new resumes were')} processed today")
    if ctx["attention"]:
        lines.append(f"- {_plural(ctx['attention'], 'resume needs', 'resumes need')} attention (unreadable files)")
    status = ("Here's where things stand today:\n" + "\n".join(lines)) if lines else "Everything is up to date."
    text = (f"{_part_of_day(now)}, {first_name}!{role_hint} {status}\n\n"
            "What would you like to do? I can find candidates for a job order, or answer questions about "
            "your candidate pool, with every answer linked to the resumes.")
    sugg = (["Who are the top candidates for this role?"] if jo else
            ([f"Who fits JO-{ctx['no_run_id']:02d}?"] if ctx["no_run_id"] else []) +
            ["Texas PEs in DFW with drainage experience", "Licensed architects in Houston with healthcare work"])
    return text, sugg[:3]


HELP_TEXT = """I search your candidates' resumes and answer with citations to the exact resume lines. You can:

- **Ask about the pool:** "Texas PEs in DFW with drainage experience and 8+ years"
- **Narrow down an answer:** "which of those have PMP?" or "only the ones open to relocation"
- **Find people for a job order:** "who fits JO-03?", or open a job order and click **Ask about this role**
- **Compare candidates:** "compare the top two on hospital experience"

Licenses, years and locations are checked by code against the resumes, and every quote is verified. I never share contact details."""

UNCLEAR_TEXTS = ["Sorry, I didn't catch that. Try asking about a role, license, location or skill.",
                 "Hmm, I'm not sure what you meant. You could ask something like \"structural engineers in Houston "
                 "with a Texas PE\"."]

OFF_TOPIC_TEXT = ("I can only help with your candidates and job orders, for example "
                  "\"structural engineers in Houston with a Texas PE\". I also never share contact details "
                  "like emails or phone numbers.")


def intro_message(jo: dict) -> tuple[str, list[str]]:
    spec = jo["spec"]
    musts = [r["text"] for r in spec.get("requirements", []) if r.get("priority") == "must"]
    text = (f"This chat is about **{spec.get('title')}** (JO-{jo['id']:02d}"
            f"{', ' + spec['metro'] if spec.get('metro') else ''}). "
            + (f"Must-haves: {'; '.join(musts)}. " if musts else "")
            + "Ask me to find candidates for it, or ask about specific requirements.")
    return text, ["Who are the top candidates for this role?", "Who has the strongest experience for the must-haves?"]


# ---------- job orders ----------

def job_order_plan(jo: dict) -> dict:
    """A search plan straight from the job order's structured requirements (no 'understand' call)."""
    spec = JobSpec.model_validate(jo["spec"])
    filters = hard_filters(spec)[0][1]
    soft = [r.text for r in spec.requirements if r.kind in ("software", "sector", "specialty", "other")]
    query = "; ".join([spec.title, spec.subdiscipline or "", *soft])
    return {"filters": filters.model_dump(), "search_query": query.strip("; ")}


async def load_job_order(job_order_id: int | None) -> dict | None:
    if not job_order_id:
        return None
    async with pool().connection() as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute("SELECT id, title, spec, status FROM job_orders WHERE id = %s", (job_order_id,))
        return await cur.fetchone()


# ---------- one turn ----------

async def respond(message: str, history: list[dict], user: dict, conv_jo: dict | None) -> dict:
    """Return the assistant message fields: kind, content, response, suggestions, person_ids, cost_usd."""
    r, meta = await route(message, history, conv_jo)
    cost = meta["cost_usd"]
    first_name = (user.get("display_name") or user.get("username") or "there").split()[0]

    if r.intent == "unclear":
        return {"kind": "off_topic", "content": random.choice(UNCLEAR_TEXTS), "response": None,
                "suggestions": ["What can you do?", "Texas PEs in DFW with drainage experience"], "person_ids": [],
                "cost_usd": cost}
    if r.intent in ("greeting", "off_topic") and r.reply.strip():   # model-written small talk, grounded in today
        return {"kind": r.intent, "content": r.reply.strip(), "response": None,
                "suggestions": ["Texas PEs in DFW with drainage experience"] if r.intent == "off_topic" else [],
                "person_ids": [], "cost_usd": cost}
    if r.intent == "greeting":
        first = meta.get("flavor") == "hello" and await _first_chat_today(user["id"])
        ctx = await _today_context() if first else None
        text, sugg = greeting_reply(meta.get("flavor", "hello"), first_name, first, ctx,
                                    datetime.now(LOCAL_TZ), conv_jo)
        return {"kind": "greeting", "content": text, "response": None, "suggestions": sugg, "person_ids": [],
                "cost_usd": cost}
    if r.intent == "help":
        return {"kind": "help", "content": HELP_TEXT, "response": None,
                "suggestions": ["Texas PEs in DFW with drainage experience"], "person_ids": [], "cost_usd": cost}
    if r.intent == "off_topic":
        return {"kind": "off_topic", "content": OFF_TOPIC_TEXT, "response": None, "suggestions": [],
                "person_ids": [], "cost_usd": cost}

    question = r.standalone_question.strip() or message
    plan_override, person_ids, kind = None, None, r.intent
    if r.intent == "job_order":
        jo = await load_job_order(r.job_order_id) or conv_jo
        if jo:
            plan_override = job_order_plan(jo)
        else:   # unknown job order number: answer as a normal search
            kind = "search"
    if r.intent == "follow_up" and r.scope == "previous_candidates":
        last = next((m for m in reversed(history) if m["role"] == "assistant" and m["kind"] in SEARCH_KINDS), None)
        if last and last.get("person_ids"):
            person_ids = list(last["person_ids"])   # the candidates that answer discussed
    if r.intent == "follow_up" and person_ids is None:
        kind = "search" if not history else "follow_up"

    result = await run_rag(question, plan_override=plan_override, person_ids=person_ids, run_name=f"ask.{kind}")
    result["standalone_question"] = question
    result["question"] = message
    if person_ids is not None and not result["candidates"]:
        n = len(person_ids)
        result["answer"] = (f"None of the {_plural(n, 'candidate', 'candidates')} from the previous answer match that. "
                            "Want me to search the whole candidate pool instead?")
        whole = re.sub(r"(?i)(of )?the candidates from the previous answer,?\s*", "", question).strip()
        return {"kind": kind, "content": result["answer"], "response": result,
                "suggestions": [f"Search everyone: {whole}"[:120]], "person_ids": person_ids,
                "cost_usd": cost + (result.get("cost_usd") or 0)}
    # Follow-ups narrow down the candidates the answer discussed (cited); fall back to the top ones shown
    cited = []
    for c in result["citations"]:
        if c["person_id"] not in cited:
            cited.append(c["person_id"])
    shown = cited or [c["person_id"] for c in result["candidates"][:10]]
    sugg = []
    if result["candidates"]:
        sugg = ["Which of these are open to relocation?", "Compare the top two"]
        if kind == "job_order":
            sugg = ["Which of these have the strongest must-have evidence?", "Compare the top two"]
    return {"kind": kind, "content": result["answer"], "response": result, "suggestions": sugg,
            "person_ids": shown, "cost_usd": cost + (result.get("cost_usd") or 0)}
