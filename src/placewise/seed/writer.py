"""Write resume text from facts with an LLM (LangChain + Claude Haiku), then fact-check it.

Flow per candidate: prompt → resume text → fact check → if problems, retry with the problems
fed back (max 2 retries) → accepted text, or a rejection recorded in the results.
Runs many candidates concurrently with a cap, and tracks tokens and cost.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from . import prompts
from .facts import CandidateFacts
from .factcheck import check, must_include

PROMPT_NAME, PROMPT_VERSION = "seed_resume_writer", 2
# USD per 1M tokens for claude-haiku-5-5 (platform.claude.com/docs pricing, checked 2026-10-22)
PRICE_IN, PRICE_OUT = 0.10, 0.50

PERSONA = {
    "concise": "terse and bullet-heavy; short bullets, no fluff",
    "narrative": "flowing sentences; a short summary paragraph and descriptive bullets",
    "senior_exec": "senior leader; executive summary, leadership and client relationships emphasized",
    "junior_academic": "early-career; education near the top, internships or academic projects framed as experience",
    "technical_detail": "technical; tools, methods and design responsibilities emphasized",
}
LENGTH = {"short": "about 200-300 words", "medium": "about 400-550 words", "long": "about 700-900 words"}
HEADERS = {
    "standard": "conventional (Summary, Experience, Education, Licenses & Certifications, Skills)",
    "caps": "ALL CAPS conventional headings (PROFESSIONAL EXPERIENCE, EDUCATION, ...)",
    "unusual": "unconventional headings (e.g. 'Where I've Worked', 'Registrations', 'Toolbox', 'Selected Work')",
}
LAYOUT = {
    "classic": "one column, contact block at top",
    "modern": "one column, skills listed near the top",
    "two_column": "write a 'Sidebar' section first (contact, skills, credentials) then the main column",
    "ats_plain": "very plain, no decoration, simple dashes for bullets",
    "compact": "dense; combine short sections",
}


@dataclass
class WriteResult:
    candidate_id: str
    text: str | None = None
    attempts: int = 0
    problems: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.text is not None

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1e6 * PRICE_IN + self.output_tokens / 1e6 * PRICE_OUT


def facts_for_writer(c: CandidateFacts) -> dict:
    """Only what a resume would contain. No answer-key labels (split, tricky flags, license_codes)."""
    return {
        "name": c.full_name, "email": c.email, "phone": c.phone, "location": f"{c.city}, {c.state}",
        "open_to_relocation": c.open_to_relocation, "discipline": c.discipline.replace("_", " "),
        "specialty": c.subdiscipline,
        "jobs": [{"title": j.title, "employer": j.employer, "location": f"{j.city}, {j.state}",
                  "start": j.start_text, "end": j.end_text,
                  "projects": [{"name": p.name, "sector": p.sector,
                                "value": f"${p.value_usd / 1e6:,.0f}M" if p.value_usd else None}
                               for p in j.projects]} for j in c.jobs],
        "credentials": [cr.text for cr in c.credentials],
        "software": c.software, "sectors": c.sectors,
        "education": [{"degree": e.degree, "school": e.school, "year": e.year} for e in c.education],
    }


def build_messages(c: CandidateFacts) -> list:
    p = prompts.load(PROMPT_NAME, PROMPT_VERSION)
    user = p["user"].format(
        persona_hint=PERSONA[c.style.persona], length_hint=LENGTH[c.style.length],
        header_hint=HEADERS[c.style.header_style], layout_hint=LAYOUT[c.style.template],
        must_include="\n  ".join(f"- {s}" for s in must_include(c)),
        facts_json=json.dumps(facts_for_writer(c), indent=1),
    )
    return [SystemMessage(p["system"]), HumanMessage(user)]


def _text_of(msg: AIMessage) -> str:
    if isinstance(msg.content, str):
        return msg.content.strip()
    return "".join(b.get("text", "") for b in msg.content if isinstance(b, dict)).strip()


async def write_one(model: ChatAnthropic, c: CandidateFacts, sem: asyncio.Semaphore,
                    max_retries: int = 2) -> WriteResult:
    res = WriteResult(candidate_id=c.candidate_id)
    messages = build_messages(c)
    t0 = time.perf_counter()
    async with sem:
        for attempt in range(1, max_retries + 2):
            res.attempts = attempt
            try:
                msg = await model.ainvoke(messages)
            except Exception as e:
                res.problems = [f"api error: {type(e).__name__}: {e}"]
                # 4xx request errors are permanent: retrying can't fix them. (Rate limits and
                # 5xx are already retried with backoff inside the SDK, max_retries=4.)
                status = getattr(e, "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break
                await asyncio.sleep(min(2 ** attempt, 10))
                continue
            u = msg.usage_metadata or {}
            res.input_tokens += u.get("input_tokens", 0)
            res.output_tokens += u.get("output_tokens", 0)
            text = _text_of(msg)
            problems = check(text, c)
            if not problems:
                res.text, res.problems = text, []
                break
            res.problems = problems
            messages = [*messages, AIMessage(text), HumanMessage(
                "The resume failed these checks:\n- " + "\n- ".join(problems[:12]) +
                "\nRewrite the full resume fixing every problem. Output only the resume.")]
    res.seconds = round(time.perf_counter() - t0, 2)
    return res


def make_model() -> ChatAnthropic:
    model_id = prompts.load(PROMPT_NAME, PROMPT_VERSION)["model"]
    # No `temperature`: Claude 5.5 models reject it (400 "temperature is deprecated").
    # Variety comes from the persona/layout/length instructions instead.
    return ChatAnthropic(model=model_id, max_tokens=3000, max_retries=4, timeout=90)


async def write_many(cands: list[CandidateFacts], concurrency: int = 8, on_done=None) -> list[WriteResult]:
    model = make_model()
    sem = asyncio.Semaphore(concurrency)

    async def run(c):
        r = await write_one(model, c, sem)
        if on_done:
            on_done(r)
        return r

    return await asyncio.gather(*(run(c) for c in cands))
